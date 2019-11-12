#!/bin/bash -eE

export FIFO_NAME=itest/itest_output_$$
export DEBUG=${DEBUG:-false}
if [ "$DEBUG" = "true" ]; then set -x; fi
export CONTAINER_NAME=pidtree-itest_$$

# The container takes a while to bootstrap so we have to wait before we emit the test event
SPIN_UP_TIME=20
# We also need to timout the test if the test event *isn't* caught
TIMEOUT=30

function create_event {
  echo "Creating test listener"
  nc -l -p 31337 & < README.md
  echo "Sleeping $SPIN_UP_TIME for pidtree-bcc to start"
  sleep $SPIN_UP_TIME
  echo "Making test connection"
  nc 127.1.33.7 31337 & > /dev/null
  CLIENT_PID=$!
  sleep 3s
  echo "Killing test connection"
  kill $CLIENT_PID
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
    RESULTS="$(echo "$line" | jq -r '. | select( .daddr == "127.1.33.7" ) | select( .port == 31337) | .proctree[0].cmdline' 2>&1)"
    if [ "$RESULTS" = "nc 127.1.33.7 31337" ]; then
      echo "Caught test traffic on 127.1.33.7:31337!"
      return 0
    elif [ "$DEBUG" = "true" ]; then
      echo "DEBUG: \$RESULTS is $RESULTS"
      echo "DEBUG: \$line is $line"
    fi
  done < "$FIFO_NAME"
}

function main {
  echo "Building itest image"
  docker build -t pidtree-itest .
  mkfifo $FIFO_NAME
  echo "Launching itest-container $CONTAINER_NAME"
  docker run --name $CONTAINER_NAME -d\
      --rm --privileged --cap-add sys_admin --pid host \
      -v $(git rev-parse --show-toplevel)/itest/example_config.yml:/work/config.yml \
      -v $(git rev-parse --show-toplevel)/$FIFO_NAME:/work/outfile \
      pidtree-itest -c /work/config.yml -f /work/outfile
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
  trap cleanup EXIT
  main "$@"
fi
