.PHONY: dev-env

default: dev-env

venv:
	virtualenv --system-site-packages -p python2 venv

dev-env: venv
	bash -c "\
		source venv/bin/activate &&\
		pip install -rrequirements.txt"

docker-env:
	pip install -rrequirements.txt

docker-run:
	docker build -t pidtree-bcc .
	docker run --privileged --cap-add sys_admin --pid host --rm -it pidtree-bcc

docker-interactive:
	# If you want to run manually inside the container, first you need to:
	# ./setup.sh
	# then you can run:
	# `python2 main.py -c example_config.yml`
	# Additionally there's a `-p` flag for printing out the templated out eBPF C code so you can debug it
	docker build -t pidtree-bcc .
	docker run --privileged --cap-add sys_admin --pid host --rm -it pidtree-bcc /bin/bash
