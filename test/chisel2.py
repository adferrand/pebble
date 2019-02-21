"""
A simple client that uses the Python ACME library to run a test issuance against
a local Pebble server. Unlike chisel.py this version implements the most recent
version of the ACME specification. Usage:

$ virtualenv venv
$ . venv/bin/activate
$ pip install -r requirements.txt
$ python chisel.py foo.com bar.com
"""
from __future__ import print_function
import json
import logging
import os
import ssl
import sys
import signal
import threading
import time
try:
    from urllib.request import urlopen
    from urllib.error import URLError
except ImportError:
    from urllib2 import urlopen
    from urllib2 import URLError

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography import x509
from cryptography.hazmat.primitives import hashes

import OpenSSL
import josepy

from acme import challenges
from acme import client as acme_client
from acme import crypto_util as acme_crypto_util
from acme import errors as acme_errors
from acme import messages
from acme import standalone

logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(int(os.getenv('LOGLEVEL', 0)))

DIRECTORY = os.getenv('DIRECTORY', 'https://localhost:14000/dir')
ACCEPTABLE_TOS = os.getenv('ACCEPTABLE_TOS',"data:text/plain,Do%20what%20thou%20wilt")
PORT = os.getenv('PORT', '5002')

# URLs to control dns-test-srv
SET_TXT = "http://localhost:8055/set-txt"
CLEAR_TXT = "http://localhost:8055/clear-txt"

def wait_for_acme_server():
    """Wait for directory URL set in the DIRECTORY env variable to respond"""
    try:
        ctx = ssl.create_default_context()
    except AttributeError:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    while True:
        try:
            urlopen(DIRECTORY, context=ctx)
            break
        except URLError as e:
            print(e)
            time.sleep(0.1)

def make_client(email=None):
    """Build an acme.Client and register a new account with a random key."""
    key = josepy.JWKRSA(key=rsa.generate_private_key(65537, 2048, default_backend()))

    net = acme_client.ClientNetwork(key, user_agent="Boulder integration tester")
    directory = messages.Directory.from_json(net.get(DIRECTORY).json())
    client = acme_client.ClientV2(directory, net)
    tos = client.directory.meta.terms_of_service
    if tos == ACCEPTABLE_TOS:
        net.account = client.new_account(messages.NewRegistration.from_data(email=email,
            terms_of_service_agreed=True))
    else:
        raise Exception("Unrecognized terms of service URL %s" % tos)
    return client

def get_chall(authz, typ):
    for chall_body in authz.body.challenges:
        if isinstance(chall_body.chall, typ):
            return chall_body
    raise Exception("No %s challenge found" % typ)

class ValidationError(Exception):
    """An error that occurs during challenge validation."""
    def __init__(self, domain, problem_type, detail, *args, **kwargs):
        self.domain = domain
        self.problem_type = problem_type
        self.detail = detail

    def __str__(self):
        return "%s: %s: %s" % (self.domain, self.problem_type, self.detail)

def make_csr(domains):
    key = OpenSSL.crypto.PKey()
    key.generate_key(OpenSSL.crypto.TYPE_RSA, 2048)
    pem = OpenSSL.crypto.dump_privatekey(OpenSSL.crypto.FILETYPE_PEM, key)
    return acme_crypto_util.make_csr(pem, domains, False)

def http_01_answer(client, chall_body):
    """Return an HTTP01Resource to server in response to the given challenge."""
    response, validation = chall_body.response_and_validation(client.net.key)
    return standalone.HTTP01RequestHandler.HTTP01Resource(
          chall=chall_body.chall, response=response,
          validation=validation)

def auth_and_issue(domains, chall_type="http-01", email=None, cert_output=None, client=None):
    """Make authzs for each of the given domains, set up a server to answer the
       challenges in those authzs, tell the ACME server to validate the challenges,
       then poll for the authzs to be ready and issue a cert."""
    if client is None:
        client = make_client(email)

    csr_pem = make_csr(domains)
    order = client.new_order(csr_pem)
    authzs = order.authorizations

    if chall_type == "http-01":
        cleanup = do_http_challenges(client, authzs)
    elif chall_type == "dns-01":
        cleanup = do_dns_challenges(client, authzs)
    else:
        raise Exception("invalid challenge type %s" % chall_type)

    try:
        order = client.poll_and_finalize(order)
    finally:
        cleanup()

    return order

def do_dns_challenges(client, authzs):
    cleanup_hosts = []
    for a in authzs:
        c = get_chall(a, challenges.DNS01)
        name, value = (c.validation_domain_name(a.body.identifier.value),
            c.validation(client.net.key))
        cleanup_hosts.append(name)
        urlopen(SET_TXT,
            data=json.dumps({
                "host": name + ".",
                "value": value,
            })).read()
        client.answer_challenge(c, c.response(client.net.key))
    def cleanup():
        for host in cleanup_hosts:
            urlopen(CLEAR_TXT,
                data=json.dumps({
                    "host": host + ".",
                })).read()
    return cleanup

def do_http_challenges(client, authzs):
    port = int(PORT)
    challs = [get_chall(a, challenges.HTTP01) for a in authzs]
    answers = set([http_01_answer(client, c) for c in challs])
    server = standalone.HTTP01Server(("", port), answers)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()

    # cleanup has to be called on any exception, or when validation is done.
    # Otherwise the process won't terminate.
    def cleanup():
        server.shutdown()
        server.server_close()
        thread.join()

    try:
        # Loop until the HTTP01Server is ready.
        while True:
            try:
                urlopen("http://localhost:%d" % port)
                break
            except URLError:
                time.sleep(0.1)

        for chall_body in challs:
            client.answer_challenge(chall_body, chall_body.response(client.net.key))
    except Exception:
        cleanup()
        raise

    return cleanup

def expect_problem(problem_type, func):
    """Run a function. If it raises a ValidationError or messages.Error that
       contains the given problem_type, return. If it raises no error or the wrong
       error, raise an exception."""
    ok = False
    try:
        func()
    except ValidationError as e:
        if e.problem_type == problem_type:
            ok = True
        else:
            raise
    except messages.Error as e:
        if problem_type in e.__str__():
            ok = True
        else:
            raise
    if not ok:
        raise Exception('Expected %s, got no error' % problem_type)

if __name__ == "__main__":
    # Die on SIGINT
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    domains = sys.argv[1:]
    if len(domains) == 0:
        print(__doc__)
        sys.exit(0)
    try:
        wait_for_acme_server()
        auth_and_issue(domains)
    except messages.Error as e:
        print(e)
        sys.exit(1)
