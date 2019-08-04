.PHONY: run-nodocker build

VERSION?=0.2
TAG?=v$(VERSION)
ROOTFS_TARGET?=opt/pidtree-bcc-rootfs
CONFIG_SRC?=$(shell git rev-parse --show-toplevel)/example_config.yml
BUILD_DIR=pidtree-bcc_$(VERSION)
ROOTFS=$(BUILD_DIR)/$(ROOTFS_TARGET)
REMOTE?=https://github.com/oholiab/pidtree-bcc

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

src/pidtree-bcc_$(TAG):
	mkdir -p src
	git clone $(REMOTE) src/pidtree-bcc_$(TAG)

pidtree-bcc_$(TAG).tar: src/pidtree-bcc_$(TAG)
	cd $< && git checkout $(TAG)
	cd $< && docker build -t pidtree-bcc:$(TAG) .
	docker run --name pidtree-bcc_$(TAG) --entrypoint /bin/true pidtree-bcc:$(TAG) 
	docker export -o $@ pidtree-bcc_$(TAG)
	docker rm pidtree-bcc_$(TAG)

$(ROOTFS): pidtree-bcc_$(TAG).tar
	mkdir -p $@
	# This sucks: need to be root to preserve permissions :(
	# TODO: Investigate building with user namespaces
	sudo tar xpf $< --ignore-command-error -C $@/ --exclude='dev/*'

$(BUILD_DIR)/etc/pidtree-bcc/config.yml: $(CONFIG_SRC)
	mkdir -p $(dir $@)
	cp $< $@

$(BUILD_DIR)/usr/bin/pidtree-bcc: pidtree-bcc
	mkdir -p $(dir $@)
	cp $< $@

$(BUILD_DIR)/etc/systemd/system/pidtree-bcc.service: pidtree-bcc.service
	mkdir -p $(dir $@)
	cp $< $@

$(BUILD_DIR)/DEBIAN:
	mkdir -p $@
	echo "$$CONTROL_CONTENTS" > $@/control

pidtree-bcc_$(VERSION).deb: $(BUILD_DIR)/DEBIAN $(BUILD_DIR)/etc/systemd/system/pidtree-bcc.service $(BUILD_DIR)/usr/bin/pidtree-bcc $(BUILD_DIR)/etc/pidtree-bcc/config.yml $(ROOTFS)
	sudo dpkg-deb --build $(basename $@)

run-nodocker: $(ROOTFS)
	sudo unshare --net --mount --propagation slave --uts --ipc --fork ./enter-ns.sh

clean:
	rm -rf $(BUILD_DIR)
	rm -rf pidtree-bcc_$(TAG).tar
	-rm *.deb
