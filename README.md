# pidtree-bcc
> bcc script for tracing process tree ancestry for connect syscalls

[![Build Status](https://travis-ci.org/Yelp/pidtree-bcc.svg?branch=master)](https://travis-ci.org/Yelp/pidtree-bcc)

## What
`pidtree-bcc` utilizes the [bcc toolchain](https://github.com/iovisor/bcc) to
create kprobes for (currently only) tcpv4 connect syscalls, and tracing the
ancestry of the process that made the syscall.

It also aims to have a tunable set of in-kernel filtering features in order to
prevent excessive logging for things like loopback and RFC1918 `connect`s

## Why 
Security monitoring purposes. ML based products like Amazon's GuardDuty will
tell you when hosts in your infrastructure have made "anomolous" outbound
requests, but often these are as-intended but not known about by the team
investigating the network traffic. Because of the transient nature of processes,
often any useful context is lost by the time investigation can occur.

`pidtree-bcc` is a supplementary intrusion detection system which
utilzes the eBPF kernel subsystem to notify a userland daemon of all
events so that they can be traced. It enables engineers to quickly
identify familiar process trees (for instance, a familiar service name
which corresponds to domain names associated with the destination IP
address) or another engineer as the originator of request via the
username associated with the process.

## Caveats
* bcc compiles your eBPF "program" to bytecode at runtime using LLVM,
  and as such needs LLVM installed and the appropriate kernel headers.
* The current implementation only supports TCP and ipv4.
* The userland daemon is likely susceptible to interference or denial of
  service, however the main aim of the project is to reduce the MTTR for
  "business as usual" events - that is to make so engineers spend less time
  chasing events that were not actually suspicious
* It's possible to cause a race condition in the userland daemon in that
  the process or parent process that triggers the kprobe may in fact
  exit before the userland daemon tries to inspect it. Setting niceness
  values might help, but it is better to consider loopback addresses to
  be out-of-scope.
* This is currently pinned to python2 because python3 did not work at
  the time of the initial hackathon project. We'll get round to it :)

## Dependencies 
See the installation instructions for [bcc](https://github.com/iovisor/bcc)

Most notably, you need a kernel with eBPF enabled (4.4 onward) and the
Linux headers for your running kernel version installed. For a
quick-start, there is a Dockerfile included and a make target (`make
docker-run`) to launch pidtree-bcc. Following the thread here is the
best way to get a full view of the requisite state of the system for
pidtree-bcc to work.

## Usage 
> CAUTION! The Makefile calls 'docker run' with `--priveleged` so it is your
> responsibility to ensure that it's not going to do anything untoward!

With docker installed:
```
make docker-run
```

... and you should see json output detailing the process tree for any process
making TCP ipv4 `connect` syscalls like this one of me connecting to Freenode in weechat.
```json
{
  "proctree": [
    {
      "username": "oholiab",
      "cmdline": "weechat",
      "pid": 1775
    },
    {
      "username": "oholiab",
      "cmdline": "weechat",
      "pid": 23769
    },
    {
      "username": "oholiab",
      "cmdline": "-zsh",
      "pid": 23231
    },
    {
      "username": "oholiab",
      "cmdline": "tmux",
      "pid": 1923
    },
    {
      "username": "root",
      "cmdline": "/sbin/init",
      "pid": 1
    }
  ],
  "timestamp": "2019-11-12T14:24:57.532744Z",
  "pid": 1775,
  "daddr": "185.30.166.37",
  "error": "",
  "port": 6697
}
```

Notably you'll not see any for the 127/8, 169.254/16, 10/8, 192.168/16
or 172.16/12 ranges because of the subnet filters I've included in the
`example_config.yaml` eBPF program.  This is obviously not an exhaustive
list of addresses you might want to filter, so you can use the example
configuration to write your own.

Additionally, you can include config like:

```yaml
ports:
  - 22
  - 443
  - 80
```

To see *only* events for these ports.
