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

.PHONY: changelog package_%

changelog: $(VERSION_FILE)
	dch -v $(VERSION)

package_%:
	make dist/$*/pidtree-bcc_$(VERSION).deb

dist/%/pidtree-bcc_$(VERSION).deb: IMAGE_NAME=$(notdir $(basename $@))_build_$*
dist/%/pidtree-bcc_$(VERSION).deb: debian/changelog Dockerfile.%
	mkdir -p dist/$*
	cd $(TOPLEVEL)
	docker build -f packaging/Dockerfile.$* -t $(IMAGE_NAME) .
	# even though we `cd`d above, `shell pwd` will still produce the full
	# path of the *packaging* directory
	docker run --rm -v $(shell pwd)/dist/$*:/work/dist $(IMAGE_NAME)
