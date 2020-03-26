.ONESHELL:
SHELL = /bin/bash
MAKEFLAGS += --warn-undefined-variables
VERSION ?= 0.5 # FIXME: this should be specified once
TAG ?= v$(VERSION)
ROOTFS_TARGET ?= opt/pidtree-bcc-rootfs
CONFIG_SRC ?= $(shell git rev-parse --show-toplevel)/example_config.yml
BUILD_DIR = pidtree-bcc_$(VERSION)
ROOTFS = $(BUILD_DIR)/$(ROOTFS_TARGET)
REMOTE ?= https://github.com/Yelp/pidtree-bcc
PREFIX ?= usr

define CONTROL_CONTENTS
Source: https://github.com/Yelp/pidtree-bcc
Package: pidtree-bcc
Version: $(VERSION)
Section: base
Priority: optional
Architecture: amd64
Depends: python3:any (>= 3.5) llvm lsb-release bcc-tools python3-bpfcc
Build-Depends: dh-virtualenv
Maintainer: Matt Carroll <mattc@yelp.com>
Description: eBPF based intrusion detection and audit logging
endef

export CONTROL_CONTENTS

default: pidtree-bcc_$(VERSION).deb

debian/control:
	echo "$(CONTROL_CONTENTS)" > $@

local-build:
	make VERSION=$(VERSION) TAG=$(shell git rev-parse HEAD) REMOTE=$(shell git rev-parse --show-toplevel)

src/pidtree-bcc_$(TAG):
	mkdir -p src
	git clone $(REMOTE) src/pidtree-bcc_$(TAG)
	cd $@
	git checkout $(TAG)
