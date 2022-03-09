#!/bin/bash -xe

function setup {
  # In the event of running tests for a newer release on an older host
  # machine we need to forward port the kernel headers
  host_release=$1
  apt-get update
  apt-get -y install lsb-release
  source /etc/lsb-release
  if [[ "$host_release" != "$DISTRIB_CODENAME" && "$host_release" != "" ]]; then
    echo "deb http://archive.ubuntu.com/ubuntu/ ${host_release} main" >> /etc/apt/sources.list.d/forwardports.list
    echo "deb http://archive.ubuntu.com/ubuntu/ ${host_release}-updates main" >> /etc/apt/sources.list.d/forwardports.list
    echo "deb http://archive.ubuntu.com/ubuntu/ ${host_release}-security main" >> /etc/apt/sources.list.d/forwardports.list
  fi
  missing_gpg="$(apt-get update | grep 'NO_PUBKEY' | head -1)"
  if [[ "$missing_gpg" != '' ]]; then
    apt-key adv --recv-keys --keyserver keyserver.ubuntu.com $(echo "$missing_gpg" | grep -Eo '[^ ]+$')
    apt-get update
  fi
  apt-get -y install linux-headers-$(uname -r)
  if [ -f /etc/apt/sources.list.d/forwardports.list ]; then
    rm /etc/apt/sources.list.d/forwardports.list
  fi
  apt-get update
  apt-get -y install /work/dist/*.deb
}
function run {
  mount -t debugfs debugfs /sys/kernel/debug
  pidtree-bcc --help
  pidtree-bcc $@
}

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
