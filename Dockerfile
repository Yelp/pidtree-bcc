ARG     OS_RELEASE=bionic
FROM    ubuntu:${OS_RELEASE} as builder
ARG     BCC_VERSION=0.12.0

RUN     apt-get update \
        && apt-get -y install pbuilder aptitude git \
        && apt-get clean

# Clone source code
RUN     git clone --single-branch --branch "v$BCC_VERSION" https://github.com/iovisor/bcc.git
WORKDIR /bcc

# Fix release tagging
RUN     sed -i 's/git describe --abbrev=0/git describe --tags --abbrev=0/' scripts/git-tag.sh

# Build debian packages
RUN     /usr/lib/pbuilder/pbuilder-satisfydepends && ./scripts/build-deb.sh release


#----------------------------------------------------------------------------------------------
FROM    ubuntu:${OS_RELEASE}

RUN     apt-get update \
        && apt-get -y install \
            python3 \
            python3-pip \
        && apt-get clean

# Install BCC toolchain
RUN     mkdir /bcc
COPY    --from=builder /bcc/*.deb /bcc/
RUN     apt-get -y install /bcc/libbcc_*.deb /bcc/python3-bcc*.deb

# Build python environment
WORKDIR /work
COPY    requirements.txt /work/
RUN     pip3 install -r requirements.txt
ADD     . /work

ENTRYPOINT ["/work/run.sh"]
CMD     ["-c", "example_config.yml"]
