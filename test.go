package main

import (
	"context"
	"fmt"
	"net"
)

func main() {
	resolver := &net.Resolver{
		PreferGo: true,
		Dial: func(ctx context.Context, _, _ string) (net.Conn, error) {
			d := net.Dialer{}
			return d.DialContext(ctx, "udp", "4.3.2.1:404")
		},
	}
	net.DefaultResolver = resolver
	ctx, cancelfunc := context.WithTimeout(context.Background(), 30)
	defer cancelfunc()
	_, err := resolver.LookupTXT(ctx, "stupid.entry.net")

	fmt.Printf("Error is: %s\n", err)

	// Result on Linux
	// Error is: lookup stupid.entry.net on 127.0.0.53:53: dial udp 4.3.2.1:404: i/o timeout

	// Result on Windows
	// Error is: lookup stupid.entry.net: dnsquery: DNS name does not exist.
}
