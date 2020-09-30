#!/bin/bash -eE

export FIFO_NAME=itest/itest_output_$$
export TEST_SERVER_FIFO_NAME=itest/itest_server_$$
export TEST_PORT=${TEST_PORT:-31337}
export DEBUG=${DEBUG:-false}
export CONTAINER_NAME=pidtree-itest_$1_$$
export TOPLEVEL=$(git rev-parse --show-toplevel)

# The container takes a while to bootstrap so we have to wait before we emit the test event
SPIN_UP_TIME=10
# We also need to timout the test if the test event *isn't* caught
TIMEOUT=$(( SPIN_UP_TIME + 5 ))

function is_port_used {
  USED_PORTS=$(ss -4lnt | awk 'FS="[[:space:]]+" { print $4 }' | cut -d: -f2 | sort)
  if [ "$(echo "$USED_PORTS" | grep -E "^${TEST_PORT}\$")" = "$TEST_PORT" ]; then
    echo "ERROR: TEST_PORT=$TEST_PORT already in use, please reassign and try again"
    exit 2
  fi
}

function create_event {
  echo "Creating test listener"
  mkfifo $TEST_SERVER_FIFO_NAME
  cat $TEST_SERVER_FIFO_NAME | nc -l -p $TEST_PORT &
  echo "Sleeping $SPIN_UP_TIME for pidtree-bcc to start"
  sleep $SPIN_UP_TIME
  echo "Making test connection"
  nc 127.1.33.7 $TEST_PORT & > /dev/null
  CLIENT_PID=$!
  echo "lolz" > $TEST_SERVER_FIFO_NAME
  sleep 3
  echo "Killing test connection"
  kill $CLIENT_PID
  pkill cat
  rm -f $TEST_SERVER_FIFO_NAME
}

function cleanup {
  echo "CLEANUP: Caught EXIT"
  set +eE
  echo "CLEANUP: Killing container"
  docker kill $CONTAINER_NAME
  echo "CLEANUP: Removing FIFO"
  rm -f $FIFO_NAME
}

function wait_for_tame_output {
  RESULTS=0
  echo "Tailing output FIFO $FIFO_NAME to catch test traffic"
  while read line; do
    RESULTS="$(echo "$line" | jq -r ". | select( .daddr == \"127.1.33.7\" ) | select( .port == $TEST_PORT) | .proctree[0].cmdline" 2>&1)"
    if [ "$RESULTS" = "nc 127.1.33.7 $TEST_PORT" ]; then
      echo "Caught test traffic on 127.1.33.7:$TEST_PORT!"
      return 0
    elif [ "$DEBUG" = "true" ]; then
      echo "DEBUG: \$RESULTS is $RESULTS"
      echo "DEBUG: \$line is $line"
    fi
  done < "$FIFO_NAME"
  return 1
}

function main {
  if [[ $# -ne 1 && "$1" != "docker" && "$1" != "ubuntu_xenial" && "$1" != "ubuntu_bionic" ]]; then
    echo "ERROR: '$@' is not a supported argument (see 'itest/itest.sh' for options)" >&2
    exit 1
  fi
  trap cleanup EXIT
  is_port_used
  if [ "$DEBUG" = "true" ]; then set -x; fi
  mkfifo $FIFO_NAME
  if [[ "$1" = "docker" ]]; then
    echo "Building itest image"
    # Build the base image
    if [ -f /etc/lsb-release ]; then
      source /etc/lsb-release
    else
      echo "WARNING: Could not source /etc/lsb-release, tentatively creating bionic docker image"
      DISTRIB_CODENAME=bionic
    fi
    docker build -t pidtree-itest-base --build-arg OS_RELEASE=$DISTRIB_CODENAME .
    # Run the setup.sh install steps in the image so we don't hit timeouts
    docker build -t pidtree-itest itest/
    echo "Launching itest-container $CONTAINER_NAME"
    docker run --name $CONTAINER_NAME -d\
        --rm --privileged --cap-add sys_admin --pid host \
        -v $TOPLEVEL/itest/example_config.yml:/work/config.yml \
        -v $TOPLEVEL/$FIFO_NAME:/work/outfile \
        pidtree-itest -c /work/config.yml -f /work/outfile
  elif [[ "$1" = "ubuntu_xenial" || "$1" = "ubuntu_bionic" ]]; then
    if [ -f /etc/lsb-release ]; then
      source /etc/lsb-release
    else
      echo "WARNING: Could not source /etc/lsb-release - I do not know what distro we are on, you could experience weird effects as this is not supported outside of Ubuntu" >&2
    fi
    mkdir -p itest/dist/$1/
    rm -f itest/dist/$1/*.deb
    cp $(ls -t packaging/dist/$1/*.deb | head -n 1) itest/dist/$1/
    docker build -t pidtree-itest-$1 -f itest/Dockerfile.ubuntu \
        --build-arg OS_RELEASE=${1/ubuntu_/} --build-arg HOSTRELEASE=$DISTRIB_CODENAME itest/
    docker run --name $CONTAINER_NAME -d\
        --rm --privileged --cap-add sys_admin --pid host \
        -v $TOPLEVEL/itest/example_config.yml:/work/config.yml \
        -v $TOPLEVEL/$FIFO_NAME:/work/outfile \
        -v $TOPLEVEL/itest/dist/$1/:/work/dist \
        -v $TOPLEVEL/itest/deb_package_itest.sh:/work/deb_package_itest.sh \
        pidtree-itest-$1 /work/deb_package_itest.sh run -c /work/config.yml -f /work/outfile
  fi
  export -f wait_for_tame_output
  export -f cleanup
  timeout $TIMEOUT bash -c wait_for_tame_output &
  WAIT_FOR_OUTPUT_PID=$!
  create_event &
  set +e
  wait $WAIT_FOR_OUTPUT_PID
  if [ $? -ne 0 ]; then
    echo "FAILED! (timeout)"
    exit 1
  else
    echo "SUCCESS!"
    exit 0
  fi
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
