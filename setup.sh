#!/bin/bash -e

DEBUG_PATH=/sys/kernel/debug
INSTALL_ONLY=${INSTALL_ONLY:-false}

apt-get update
if ! apt-get -y install "linux-headers-$(uname -r)"; then
    # headers for this specific version are no longer available
    # we can try to approximate using the metapackage and cross fingers
    kernel_flavour=$(uname -r | rev | cut -d - -f 1 | rev)
    apt-get -y install "linux-headers-$kernel_flavour"
fi

if [ "$INSTALL_ONLY" = "true" ]; then exit 0; fi

if  ! mountpoint -q $DEBUG_PATH; then
    mount -t debugfs debugfs $DEBUG_PATH
fi
