#!/bin/bash -eE

export OUTPUT_NAME=itest/itest_output_$$
export TEST_CONNECT_PORT=${TEST_CONNECT_PORT:-31337}
export TEST_LISTEN_PORT=${TEST_LISTEN_PORT:-41337}
export TEST_LISTEN_TIMEOUT=${TEST_LISTEN_TIMEOUT:-5}
export DEBUG=${DEBUG:-false}
export CONTAINER_NAME=pidtree-itest_$1_$$
export TOPLEVEL=$(git rev-parse --show-toplevel)

# The container takes a while to bootstrap so we have to wait before we emit the test event
SPIN_UP_TIME=5
# We also need to timout the test if the test event *isn't* caught
TIMEOUT=$(( SPIN_UP_TIME + 5 ))
# Format: test_name:test_event_generator:test_flag_to_match
TEST_CASES=(
  "tcp_connect:create_connect_event:nc -w 1 127.1.33.7 $TEST_CONNECT_PORT"
  "net_listen:create_listen_event:nc -w $TEST_LISTEN_TIMEOUT -lnp $TEST_LISTEN_PORT"
)

function is_port_used {
  USED_PORTS=$(ss -4lnt | awk 'FS="[[:space:]]+" { print $4 }' | cut -d: -f2 | sort)
  if [ "$(echo "$USED_PORTS" | grep -E "^${1}\$")" = "$1" ]; then
    echo "ERROR: port $1 already in use, please reassign and try again"
    exit 2
  fi
}

function create_connect_event {
  echo "Creating test listener"
  nc -w $TEST_LISTEN_TIMEOUT -l -p $TEST_CONNECT_PORT &
  listener_pid=$!
  sleep 1
  echo "Making test connection"
  nc -w 1 127.1.33.7 $TEST_CONNECT_PORT
  wait $listener_pid
}

function create_listen_event {
  echo "Creating test listener"
  sleep 1
  nc -w $TEST_LISTEN_TIMEOUT -lnp $TEST_LISTEN_PORT
}

function cleanup {
  echo "CLEANUP: Caught EXIT"
  set +eE
  echo "CLEANUP: Killing container"
  docker kill $CONTAINER_NAME
  echo "CLEANUP: Removing FIFO"
  rm -f $OUTPUT_NAME
}

function wait_for_tame_output {
  echo "Tailing output $OUTPUT_NAME to catch test traffic '$1'"
  tail -n0 -f $OUTPUT_NAME | while read line; do
    if echo "$line" | grep "$1"; then
      echo "Caught test traffic matching '$1'"
      exit 0
    elif [ "$DEBUG" = "true" ]; then
      echo "DEBUG: \$line is $line"
    fi
  done
}

function main {
  if [[ $# -ne 1 && "$1" != "docker" && "$1" != "ubuntu_xenial" && "$1" != "ubuntu_bionic" ]]; then
    echo "ERROR: '$@' is not a supported argument (see 'itest/itest.sh' for options)" >&2
    exit 1
  fi
  trap cleanup EXIT
  is_port_used $TEST_CONNECT_PORT
  is_port_used $TEST_LISTEN_PORT
  if [ "$DEBUG" = "true" ]; then set -x; fi
  touch $OUTPUT_NAME
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
        -v $TOPLEVEL/$OUTPUT_NAME:/work/outfile \
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
    docker run --name $CONTAINER_NAME -d \
        --rm --privileged --cap-add sys_admin --pid host \
        -v $TOPLEVEL/itest/example_config.yml:/work/config.yml \
        -v $TOPLEVEL/$OUTPUT_NAME:/work/outfile \
        -v $TOPLEVEL/itest/dist/$1/:/work/dist \
        -v $TOPLEVEL/itest/deb_package_itest.sh:/work/deb_package_itest.sh \
        pidtree-itest-$1 /work/deb_package_itest.sh run -c /work/config.yml -f /work/outfile
  fi
  echo "Sleeping $SPIN_UP_TIME seconds for pidtree-bcc to start"
  sleep $SPIN_UP_TIME
  export -f wait_for_tame_output
  export -f cleanup
  EXIT_CODE=0
  for test_case in "${TEST_CASES[@]}"; do
    test_name=$(echo "$test_case" | cut -d: -f1)
    test_event=$(echo "$test_case" | cut -d: -f2)
    test_check=$(echo "$test_case" | cut -d: -f3)
    timeout $TIMEOUT bash -c "wait_for_tame_output '$test_check'" &
    WAIT_FOR_OUTPUT_PID=$!
    $test_event &
    WAIT_FOR_MOCK_EVENT=$!
    set +e
    wait $WAIT_FOR_OUTPUT_PID
    if [ $? -ne 0 ]; then
      echo "$test_name: FAILED! (timeout)"
      EXIT_CODE=1
    else
      echo "$test_name: SUCCESS!"
      EXIT_CODE=0
    fi
    wait $WAIT_FOR_MOCK_EVENT
  done
  exit $EXIT_CODE
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
