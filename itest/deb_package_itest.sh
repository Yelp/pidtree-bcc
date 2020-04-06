#!/bin/bash -xe

function setup {
  # In the event of running tests for a newer release on an older host
  # machine we need to forward port the kernel headers
  host_release=$1
  apt-get update
  apt-get -y install lsb-release apt-transport-https ca-certificates gnupg
  source /etc/lsb-release
  apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 4052245BD4284CDD
  echo "deb https://repo.iovisor.org/apt/$(lsb_release -cs) $(lsb_release -cs) main" > /etc/apt/sources.list.d/iovisor.list
  if [[ "$host_release" != "$DISTRIB_CODENAME" && "$host_release" != "" ]]; then
    echo "deb http://archive.ubuntu.com/ubuntu/ ${host_release} main" >> /etc/apt/sources.list.d/forwardports.list
    echo "deb http://archive.ubuntu.com/ubuntu/ ${host_release}-updates main" >> /etc/apt/sources.list.d/forwardports.list
    echo "deb http://archive.ubuntu.com/ubuntu/ ${host_release}-security main" >> /etc/apt/sources.list.d/forwardports.list
  fi
  apt-get update
  apt-get -y install linux-headers-$(uname -r)
  rm /etc/apt/sources.list.d/forwardports.list
  apt-get update
  apt-get -y install /work/dist/*.deb
}

function run {
  mount -t debugfs debugfs /sys/kernel/debug
  pidtree-bcc $@
}

echo $@
CMD=$1
shift
if [[ "$CMD" = "setup" ]]; then
  setup $@
elif [[ "$CMD" = "run" ]]; then
  run $@
else
  setup
  run
fi
