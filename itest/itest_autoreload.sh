#!/bin/bash

export TOPLEVEL=$(git rev-parse --show-toplevel)
export CONTAINER_NAME=pidtree-autoreload-itest-$$
export OUTPUT_NAME=itest/tmp/itest-autoreload-$$
export DADDR='127.1.33.7'

mkdir -p $TOPLEVEL/itest/tmp/autoreload

function cleanup {
    set +e
    docker kill $CONTAINER_NAME
    rm -f $TOPLEVEL/$OUTPUT_NAME
}

function create_connect_event {
    echo "Creating connection event"
    nc -w 2 -l -p 41337 -s $1 &
    listener_pid=$!
    sleep 1
    nc -w 1 $1 41337
    wait $listener_pid
    echo "Connection event completed"
}

function test_output {
    echo "Waiting for pidtree-bcc output, looking for $DADDR"
    create_connect_event $DADDR &
    connect_pid=$!
    tail -n0 -f $OUTPUT_NAME | while read line; do
        if echo "$line" | grep "$DADDR"; then
            echo "Caught test traffic"
            pkill -x --parent $$ tail
            break
        fi
    done
    wait $connect_pid
    exit 0
}

function write_config {
    cp $TOPLEVEL/itest/config_autoreload.yml $TOPLEVEL/itest/tmp/autoreload/config.yml
    sed "s/<net_address>/$1/g" $TOPLEVEL/itest/config_filters_autoreload.yml > $TOPLEVEL/itest/tmp/autoreload/filters.yml
}

trap cleanup INT EXIT

touch $TOPLEVEL/$OUTPUT_NAME

if [ -f /etc/lsb-release ]; then
    source /etc/lsb-release
else
    echo "WARNING: Could not source /etc/lsb-release, tentatively creating jammy docker image"
    DISTRIB_CODENAME=jammy
fi
docker build -t pidtree-itest-base --build-arg OS_RELEASE=$DISTRIB_CODENAME .
docker build -t pidtree-itest itest

echo "Creating background pidtree-bcc container to catch traffic"
write_config $DADDR
docker run --name $CONTAINER_NAME --rm -d \
    --privileged --cap-add sys_admin --pid host \
    -v $TOPLEVEL/itest/tmp/autoreload:/work/config \
    -v $TOPLEVEL/$OUTPUT_NAME:/work/output \
    pidtree-itest -c /work/config/config.yml -f /work/output -w --health-check-period 1

echo "Waiting a bit to let pidtree bootstrap"
sleep 15

export -f test_output
export -f create_connect_event

timeout 10s bash -c test_output
if [ $? -eq 0 ]; then
    echo "ERRROR: first connection even should have been filtered"
    exit 1
fi

echo "Changing configuration values and waiting for hot-swap"
write_config 1.1.1.1
sleep 5

timeout 20s bash -c test_output
if [ $? -eq 0 ]; then
    echo "SUCCESS!"
    exit 0
else
    echo "FAILED! (timeout)"
    exit 1
fi
