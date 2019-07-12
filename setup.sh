#!/bin/bash

apt-get update
apt-get -y install linux-headers-$(uname -r)
mount -t debugfs debugfs /sys/kernel/debug
