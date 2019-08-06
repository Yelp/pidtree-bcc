#!/bin/bash

apt-get update >/dev/null
apt-get -y install linux-headers-$(uname -r)
mount -t debugfs debugfs /sys/kernel/debug
