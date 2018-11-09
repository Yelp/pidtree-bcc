.PHONY: dev-env

default: dev-env

venv:
	virtualenv -p python2 --system-site-packages venv

dev-env: venv
	bash -c "\
		source venv/bin/activate &&\
		pip install -rrequirements.txt"
