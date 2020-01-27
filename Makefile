.PHONY: dev-env itest test-all
FIFO=$(CURDIR)/pidtree-bcc.fifo
EXTRA_DOCKER_ARGS?=""
DOCKER_ARGS=$(EXTRA_DOCKER_ARGS) -v /etc/passwd:/etc/passwd:ro --privileged --cap-add sys_admin --pid host

default: dev-env

venv:
	virtualenv --system-site-packages -p python3 venv

dev-env: venv
	bash -c "\
		source venv/bin/activate &&\
		pip install -rrequirements.txt"

docker-env:
	pip3 install -rrequirements.txt

docker-run:
	docker build -t pidtree-bcc .
	docker run $(DOCKER_ARGS) --rm -it pidtree-bcc -c example_config.yml

docker-run-with-fifo:
	mkfifo pidtree-bcc.fifo || true
	docker build -t pidtree-bcc .
	docker run -v $(FIFO):/work/pidtree-bcc.fifo $(DOCKER_ARGS) --rm -it pidtree-bcc -c example_config.yml -f pidtree-bcc.fifo

docker-interactive:
	# If you want to run manually inside the container, first you need to:
	# ./setup.sh
	# then you can run:
	# `python2 main.py -c example_config.yml`
	# Additionally there's a `-p` flag for printing out the templated out eBPF C code so you can debug it
	docker build -t pidtree-bcc .
	docker run $(DOCKER_ARGS) --rm -it --entrypoint /bin/bash pidtree-bcc

testhosts:
	docker ps -q | xargs -n 1 docker inspect --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}} {{ .Name }}' | sed 's/ \// /' > $@

docker-run-testhosts: testhosts
	make EXTRA_DOCKER_ARGS="-v $(CURDIR)/testhosts:/etc/hosts:ro" docker-run

itest:
	./itest/itest.sh

test:
	tox

test-all:
	make test
	make itest
