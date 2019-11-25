#!/bin/bash -e

DEBUG_PATH=/sys/kernel/debug
INSTALL_ONLY=${INSTALL_ONLY:-false}

apt-get update
apt-get -y install linux-headers-"$(uname -r)"

if [ "$INSTALL_ONLY" = "true" ]; then exit 0; fi

if  ! mountpoint -q $DEBUG_PATH; then
    mount -t debugfs debugfs $DEBUG_PATH
fi
