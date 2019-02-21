$ErrorActionPreference = "Stop"

if ($env:APPVEYOR_REPO_TAG -eq "true") {
    "Publishing ..."
} else {
    "Skipping publishing"
    exit 0
}

docker login -u $env:DOCKER_USER -p $env:DOCKER_PASS

$basenames = @("pebble", "pebble-challtestsrv")
foreach ($basename in $basenames) {
    $image_name = "adferrand/$basename"
    $tag = "$env:APPVEYOR_REPO_TAG_NAME-nanoserver-sac2016"

    "Updating docker $basename image ..."

    docker build -t $image_name`:temp -f docker/$basename/Dockerfile-windows

    "Try to publish image: $image_name`:$tag"
    docker tag $image_name`:temp $image_name`:tag
    docker push $image_name`:$tag

    "Try to publish rolling image: $image_name`:nanoserver-sac2016"
    docker tag $image_name`:temp $image_name`:nanoserver-sac2016
    docker push $image_name`:nanoserver-sac2016
}
