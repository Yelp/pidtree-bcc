.PHONY: run-nodocker build

VERSION?=0.2
TAG=v$(VERSION)
ROOTFS_TARGET?=opt/pidtree-bcc-rootfs
BUILD_DIR=pidtree-bcc_$(VERSION)
ROOTFS=$(BUILD_DIR)/$(ROOTFS_TARGET)

define CONTROL_CONTENTS
Package: pidtree-bcc
Version: $(VERSION)
Section: base
Priority: optional
Architecture: x86_64
Depends: 
Maintainer: Matt Carroll <oholiab@grimmwa.re>
Description: eBPF based intrusion detection and audit logging
endef

export CONTROL_CONTENTS

pidtree-bcc_$(TAG).tar:
	docker export -o $@ pidtree-bcc:$(TAG)

$(ROOTFS): pidtree-bcc_$(TAG).tar
	mkdir -p $@
	tar xf $< --ignore-command-error -C $@/ --exclude='dev/*'

$(BUILD_DIR)/DEBIAN:
	mkdir -p $@
	echo "$$CONTROL_CONTENTS" > $@/control

run-nodocker: $(ROOTFS)
	sudo unshare --net --mount --propagation slave --uts --ipc --fork ./enter-ns.sh
