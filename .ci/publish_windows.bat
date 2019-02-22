if "%APPVEYOR_REPO_TAG%" == "true" (
    echo Publishing...
) else (
    echo Skipping publishing
)

docker login -u=%DOCKER_USER% -p=%DOCKER_PASS%

set base_names=pebble pebble-challtestsrv
(for %%a in (%base_names%) do (
    set basename="%%a"
    set image_name=adferrand/%basename%
    set tag=%APPVEYOR_REPO_TAG_NAME%-nanoserver-sac2016

    echo Updating docker %image_name% image...

    docker build -t %image_name%:temp -f docker/%base_name%/Dockerfile-windows .

    echo Try to publish image: %image_name%/%tag%
    docker tag %image_name%:temp %image_name%/%tag%
    docker push %image_name%/%tag%

    echo Try to publish rolling image: %image_name%/nanoserver-sac2016
    docker tag %image_name%:temp %image_name%/nanoserver-sac2016
    docker push %image_name%/nanoserver-sac2016
))

echo Published
