#!/bin/bash

function setup {
  apt-get update
  apt-get -y install lsb-release apt-transport-https
  apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 4052245BD4284CDD
  echo "deb https://repo.iovisor.org/apt/$(lsb_release -cs) $(lsb_release -cs) main" > /etc/apt/sources.list.d/iovisor.list
  apt-get update
  apt-get -y install linux-headers-$(uname -r)
  apt-get -y install /work/dist/*.deb
}

function run {
  mount -t debugfs debugfs /sys/kernel/debug
  pidtree-bcc $@
}

CMD=$1
shift
if [[ "$CMD" = "setup" ]]; then
  setup
elif [[ "$CMD" = "run" ]]; then
  run $@
else
  setup
  run
fi
