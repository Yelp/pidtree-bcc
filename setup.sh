#!/bin/bash

DEBUG_PATH=/sys/kernel/debug

apt-get update
apt-get -y install linux-headers-"$(uname -r)"
if  ! mountpoint -q $DEBUG_PATH; then
    mount -t debugfs debugfs $DEBUG_PATH
fi
