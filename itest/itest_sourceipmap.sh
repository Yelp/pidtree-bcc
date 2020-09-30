#!/bin/bash -e

export CONTAINER_NAME=pidtree-mapping-itest-$$
export TAME_CONTAINER_NAME=hello-$$
export FIFONAME=itest/itest-sourceip-$$

itest/gen-ip-mapping.sh itest/tmp/ipmapping.txt 2 &
MAPGEN_PID=$!

function cleanup {
    set +e
    kill $MAPGEN_PID
    docker kill $CONTAINER_NAME
    rm -f $FIFONAME
}

function test_output {
    echo "Waiting for pidtree-bcc output corresponding to container $TAME_CONTAINER_NAME"
    while read line; do
        echo $line | grep $TAME_CONTAINER_NAME
        [ $? -eq 0 ] && return 0
    done <$FIFONAME
}

trap cleanup INT EXIT

mkfifo $FIFONAME

if [ -f /etc/lsb-release ]; then
    source /etc/lsb-release
else
    echo "WARNING: Could not source /etc/lsb-release, tentatively creating bionic docker image"
    DISTRIB_CODENAME=bionic
fi
docker build -t pidtree-itest-base --build-arg OS_RELEASE=$DISTRIB_CODENAME .
docker build -t pidtree-itest itest
docker pull ubuntu:latest
echo "Creating background pidtree-bcc container to catch traffic"
docker run --name $CONTAINER_NAME --rm -d\
    --rm --privileged --cap-add sys_admin --pid host \
    -v $(git rev-parse --show-toplevel)/itest/mapping_config.yml:/work/config.yml \
    -v $(git rev-parse --show-toplevel)/itest/tmp:/maps/ \
    -v $(git rev-parse --show-toplevel)/$FIFONAME:/work/output \
    pidtree-itest -c /work/config.yml -f /work/output

echo "Creating background container $TAME_CONTAINER_NAME to send traffic"
docker run --name $TAME_CONTAINER_NAME --rm -d ubuntu:latest bash -c "sleep 15s; apt-get update"

export -f test_output
timeout 20s bash -c test_output

if [ $? -eq 0 ]; then
    echo "SUCCESS!"
    exit 0
else
    echo "FAILED! (timeout)"
    exit 1
fi
