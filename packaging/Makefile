# Set up `make`
.ONESHELL:
SHELL = /bin/bash
MAKEFLAGS += --warn-undefined-variables

# Helper variable
TOPLEVEL = $(shell git rev-parse --show-toplevel)
VERSION_FILE = $(TOPLEVEL)/pidtree_bcc/__init__.py

# Variables
VERSION ?= $(shell cd $(TOPLEVEL) && python -c "from pidtree_bcc import __version__; print(__version__)")
PREFIX ?= usr

.PHONY: changelog

default: dist/pidtree-bcc_$(VERSION).deb

changelog: $(VERSION_FILE)
	dch -v $(VERSION)

package_ubuntu_xenial: dist/pidtree-bcc_$(VERSION).deb

dist/pidtree-bcc_$(VERSION).deb: IMAGE_NAME=$(notdir $(basename $@))_build
dist/pidtree-bcc_$(VERSION).deb: debian/changelog
	mkdir -p dist
	cd $(TOPLEVEL)
	docker build -f packaging/Dockerfile.ubuntu_xenial -t $(IMAGE_NAME) .
	docker run --rm -it -v $(shell pwd)/dist:/work/dist $(IMAGE_NAME)
