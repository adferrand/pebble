docker build -f docker/pebble/Dockerfile-windows -t adferrand/pebble:nanoserver-sac2016 .
docker build -f docker/pebble-challtestsrv/Dockerfile-windows -t adferrand/pebble-challtestsrv:nanoserver-sac2016 .
docker login -u="%DOCKER_USER%" -p="%DOCKER_PASS%"
docker push adferrand/pebble:nanoserver-sac2016
docker push adferrand/pebble-challtestsrv:nanoserver-sac2016
