#!/bin/bash

apt-get -y install linux-headers-$(uname -r)
mount -t debugfs debugfs /sys/kernel/debug
