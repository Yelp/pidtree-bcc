.ONESHELL:
SHELL := /bin/bash
MAKEFLAGS += --warn-undefined-variables

.PHONY: dev-env itest test test-all cook-image docker-run docker-run-with-fifo docker-interactive testhosts docker-run-testhosts clean clean-cache install-hooks release
FIFO = $(CURDIR)/pidtree-bcc.fifo
EXTRA_DOCKER_ARGS ?=
DOCKER_ARGS = $(EXTRA_DOCKER_ARGS) -v /etc/passwd:/etc/passwd:ro --privileged --cap-add sys_admin --pid host
DOCKER_BASE_IMAGE_TMPL ?= ubuntu:OS_RELEASE_PH
HOST_OS_RELEASE = $(or $(shell cat /etc/lsb-release 2>/dev/null | grep -Po '(?<=CODENAME=)(.+)'), jammy)
SUPPORTED_UBUNTU_RELEASES = bionic focal jammy noble
UPSTREAM_BCC_RELEASES = jammy noble
VERSION_FILE = $(PWD)/pidtree_bcc/__init__.py
EDITOR ?= vi

default: venv

venv: requirements.txt requirements-dev.txt
	tox -e venv

install-hooks: venv
	venv/bin/pre-commit install -f --install-hooks

cook-image: clean-cache docker-bcc-base-$(HOST_OS_RELEASE)
	docker build -t pidtree-bcc --build-arg OS_RELEASE=$(HOST_OS_RELEASE) .

docker-run: cook-image
	docker run $(DOCKER_ARGS) --rm -it pidtree-bcc -c example_config.yml

docker-run-with-fifo: cook-image
	mkfifo pidtree-bcc.fifo || true
	docker run -v $(FIFO):/work/pidtree-bcc.fifo $(DOCKER_ARGS) --rm -it pidtree-bcc -c example_config.yml -f pidtree-bcc.fifo

docker-interactive: cook-image
	# If you want to run manually inside the container, first you need to:
	# ./setup.sh
	# then you can run:
	# `python3 main.py -c example_config.yml`
	# Additionally there's a `-p` flag for printing out the templated out eBPF C code so you can debug it
	docker run $(DOCKER_ARGS) --rm -it --entrypoint /bin/bash pidtree-bcc

testhosts:
	docker ps -q | xargs -n 1 docker inspect --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}} {{ .Name }}' | sed 's/ \// /' > $@

docker-run-testhosts: testhosts
	make EXTRA_DOCKER_ARGS="-v $(CURDIR)/testhosts:/etc/hosts:ro" docker-run

itest: clean-cache docker-bcc-base-$(HOST_OS_RELEASE)
	./itest/itest_generic.sh docker
	./itest/itest_sourceipmap.sh
	./itest/itest_autoreload.sh

docker-base-%: Dockerfile.base
	$(eval dollar_star := $(subst ubuntu_,,$*))
	docker build -t pidtree-docker-base-$(dollar_star) --build-arg BASE_IMAGE=$(subst OS_RELEASE_PH,$(dollar_star),$(DOCKER_BASE_IMAGE_TMPL)) -f Dockerfile.base .

docker-bcc-base-%: docker-base-%
	$(eval dollar_star := $(subst ubuntu_,,$*))
	docker build -t pidtree-docker-base-bcc-$(dollar_star) \
		--build-arg OS_RELEASE=$(dollar_star) \
		--build-arg BCC_TOOLS_SOURCE=$(if $(findstring $(dollar_star),$(UPSTREAM_BCC_RELEASES)),upstream,source) \
		-f Dockerfile.bcc .

itest_%: clean-cache docker-bcc-base-%
	./itest/itest_generic.sh $*

test: clean-cache
	tox

test-all: clean-cache
	set -e
	make test
	make itest
	$(foreach release, $(SUPPORTED_UBUNTU_RELEASES), make package_ubuntu_$(release);)
	$(foreach release, $(SUPPORTED_UBUNTU_RELEASES), make itest_ubuntu_$(release);)

package_%: docker-base-%
	make -C packaging package_$*

clean-cache:
	find -name '*.pyc' -delete
	find -name '__pycache__' -delete

clean: clean-cache
	rm -Rf packaging/dist itest/dist
	rm -Rf itest/tmp
	rm -Rf .tox venv

release:
	"$(EDITOR)" $(VERSION_FILE)
	make -C packaging changelog VERSION_FILE=$(VERSION_FILE)
	version=$$(grep __version__ $(VERSION_FILE) | grep -Po "(?<=')([^']+)")
	git commit -am "Release $$version"
	git tag v$$version
