#!/bin/bash

CONTAINER_NAME=pidtree-mapping-itest

./gen-ip-mapping.sh tmp/ipmapping.txt 2 &
MAPGEN_PID=$!

trap "kill $MAPGEN_PID" INT EXIT

docker run --name $CONTAINER_NAME --rm -it\
    --rm --privileged --cap-add sys_admin --pid host \
    -v $(git rev-parse --show-toplevel)/itest/mapping_config.yml:/work/config.yml \
    -v $(git rev-parse --show-toplevel)/itest/tmp:/maps/ \
    pidtree-bcc -c /work/config.yml | grep --color -E '$|"source_container": "\S*"'
