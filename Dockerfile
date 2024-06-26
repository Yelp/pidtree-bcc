ARG     OS_RELEASE=jammy
FROM    pidtree-docker-base-bcc-${OS_RELEASE}

# Build python environment
WORKDIR /work
COPY    requirements.txt /work/
RUN     pip3 install -r requirements.txt
ADD     . /work

ENTRYPOINT ["/work/run.sh"]
CMD     ["-c", "example_config.yml"]
