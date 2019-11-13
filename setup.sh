#!/bin/bash

DEBUG_PATH=/sys/kernel/debug
INSTALL_ONLY=${INSTALL_ONLY:-false}

apt-get update
apt-get -y install linux-headers-"$(uname -r)"

$INSTALL_ONLY && exit 0

if  ! mountpoint -q $DEBUG_PATH; then
    mount -t debugfs debugfs $DEBUG_PATH
fi
