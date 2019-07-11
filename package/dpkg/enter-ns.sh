#!/bin/bash
rootfs=$1
shift
args=$@
mkdir -p $rootfs/proc $rootfs/dev
mount --rbind /proc $rootfs/proc
mount --rbind /dev $rootfs/dev
exec chroot $rootfs /work/run.sh
