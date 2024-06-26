#!/bin/bash -e

export TOPLEVEL=$(git rev-parse --show-toplevel)
export CONTAINER_NAME=pidtree-mapping-itest-$$
export TAME_CONTAINER_NAME=hello-$$
export FIFONAME=itest/tmp/itest-sourceip-$$

mkdir -p $TOPLEVEL/itest/tmp

$TOPLEVEL/itest/gen-ip-mapping.sh $TOPLEVEL/itest/tmp/maps/ipmapping.txt 2 &
MAPGEN_PID=$!

function cleanup {
    set +e
    kill $MAPGEN_PID
    docker kill $CONTAINER_NAME
    rm -f $TOPLEVEL/$FIFONAME
}

function test_output {
    echo "Waiting for pidtree-bcc output corresponding to container $TAME_CONTAINER_NAME"
    while read line; do
        echo $line | grep $TAME_CONTAINER_NAME
        [ $? -eq 0 ] && return 0
    done < $TOPLEVEL/$FIFONAME
}

trap cleanup INT EXIT

mkfifo $TOPLEVEL/$FIFONAME

if [ -f /etc/lsb-release ]; then
    source /etc/lsb-release
else
    echo "WARNING: Could not source /etc/lsb-release, tentatively creating jammy docker image"
    DISTRIB_CODENAME=jammy
fi
docker build -t pidtree-itest-base --build-arg OS_RELEASE=$DISTRIB_CODENAME .
docker build -t pidtree-itest itest
docker pull ubuntu:latest
echo "Creating background pidtree-bcc container to catch traffic"
docker run --name $CONTAINER_NAME --rm -d\
    --rm --privileged --cap-add sys_admin --pid host \
    -v $TOPLEVEL/itest/config_mapping.yml:/work/config.yml \
    -v $TOPLEVEL/itest/tmp/maps:/maps/ \
    -v $TOPLEVEL/$FIFONAME:/work/output \
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
