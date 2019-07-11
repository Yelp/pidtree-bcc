.PHONY: run-nodocker build

VERSION?=0.2
TAG=v$(VERSION)
ROOTFS_TARGET?=opt/pidtree-bcc-rootfs
CONFIG_SRC?=$(shell git rev-parse --show-toplevel)/example_config.yml
BUILD_DIR=pidtree-bcc_$(VERSION)
ROOTFS=$(BUILD_DIR)/$(ROOTFS_TARGET)

define CONTROL_CONTENTS
Package: pidtree-bcc
Version: $(VERSION)
Section: base
Priority: optional
Architecture: amd64
Depends: 
Maintainer: Matt Carroll <oholiab@grimmwa.re>
Description: eBPF based intrusion detection and audit logging
endef

export CONTROL_CONTENTS

default: pidtree-bcc_$(VERSION).deb

pidtree-bcc_$(TAG).tar:
	docker export -o $@ pidtree-bcc:$(TAG)

$(ROOTFS): pidtree-bcc_$(TAG).tar
	mkdir -p $@
	tar xf $< --ignore-command-error -C $@/ --exclude='dev/*'

$(ROOTFS)/etc/pidtree-bcc/config.yml: $(CONFIG_SRC)
	mkdir -p $(dir $@)
	cp $< $@

$(ROOTFS)/usr/bin/pidtree-bcc: pidtree-bcc
	mkdir -p $(dir $@)
	cp $< $@

$(ROOTFS)/etc/systemd/system/pidtree-bcc.service: pidtree-bcc.service
	mkdir -p $(dir $@)
	cp $< $@

$(BUILD_DIR)/DEBIAN:
	mkdir -p $@
	echo "$$CONTROL_CONTENTS" > $@/control

pidtree-bcc_$(VERSION).deb: $(BUILD_DIR)/DEBIAN $(ROOTFS)/etc/systemd/system/pidtree-bcc.service $(ROOTFS)/usr/bin/pidtree-bcc $(ROOTFS)/etc/pidtree-bcc/config.yml $(ROOTFS)
	dpkg-deb --build $(basename $@)

run-nodocker: $(ROOTFS)
	sudo unshare --net --mount --propagation slave --uts --ipc --fork ./enter-ns.sh

clean:
	rm -rf pidtree-bcc_$(VERSION)
