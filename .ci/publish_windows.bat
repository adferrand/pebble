if "%APPVEYOR_REPO_TAG%" == "true" (
    echo Publishing...
) else (
    echo Skipping publishing
)

docker login -u=%DOCKER_USER% -p=%DOCKER_PASS%

set basenames=pebble pebble-challtestsrv
(for %%a in (%basenames%) do (
    set basename=%%a
    echo %basename%
    set image=adferrand/%basename%
    echo %image%
    set tag=%APPVEYOR_REPO_TAG_NAME%-nanoserver-sac2016

    echo Updating docker %image% image...

    docker build -t %image%:temp -f docker/%basename%/Dockerfile-windows .

    echo Try to publish image: %image%/%tag%
    docker tag %image%:temp %image%/%tag%
    docker push %image%/%tag%

    echo Try to publish rolling image: %image%/nanoserver-sac2016
    docker tag %image%:temp %image%/nanoserver-sac2016
    docker push %image%/nanoserver-sac2016
))

echo Published
