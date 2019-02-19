# pidtree-bcc
> bcc script for tracing process tree ancestry for connect syscalls

## What
`pidtree-bcc` utilizes the [bcc toolchain](https://github.com/iovisor/bcc) to
create kprobes for (currently only) tcpv4 connect syscalls, and tracing the
ancestry of the process that made the syscall.

It also aims to have a limited set of in-kernel filtering features in order to
prevent excessive logging for things like loopback and RFC1918 `connect`s

## Why 
Security monitoring purposes. ML based products like Amazon's GuardDuty will
tell you when hosts in your infrastructure have made "anomolous" outbound
requests, but often these are as-intended but not known about by the team
investigating the network traffic. Because of the transient nature of processes,
often any useful context is lost by the time investigation can occur.

`pidtree-bcc` is a proof of concept which utilzes the eBPF kernel subsystem to
notify a userland daemon of all events so that they can be traced. It enables
engineers to quickly identify familiar process trees (for instance, a familiar
service name which corresponds to domain names associated with the destination
IP address) or another engineer as the originator of request via the username
associated with the process.

## Caveats
* This is only a proof of concept as bcc requires LLVM to be installed on the
  system that it's invoked on as it compiles to eBPF bytecode at runtime. Having
  C compilers on production systems that don't need them is not desirable for
  security reasons. Other eBPF toolchains exist here but this was the easiest
  way to get started. We have mitigated this to some extent by running in a
  privileged docker container with access to the host's PID namespace.
* The current implementation is only for TCP and ipv4.
* The userland daemon is likely susceptible to interference or denial of
  service, however the main aim of the project is to reduce the MTTR for
  "business as usual" events - that is to make so engineers spend less time
  chasing events that were not actually suspicious
* It's possible to cause a race condition in the userland daemon in that the
  process or parent process that triggers the kprobe may in fact exit before the
  userland daemon tries to inspect it. Setting niceness values might help?
* This is currently pinned to python2 because of the way that the `bcc` AUR
  package (and subsequently the Ubuntu deb) installed on my machine - python2
  worked but python3 didn't. I'll fix that :)

## Dependencies 
See the installation instructions for [bcc](https://github.com/iovisor/bcc)

Most notably, you need a kernel with eBPF enabled.

## Usage 
> CAUTION! The Makefile calls 'docker run' with `--priveleged` so it is your
> responsibility to ensure that it's not going to do anything untoward!

With docker installed:
```
make docker-run
```

... and you should see json output detailing the process tree for any process
making TCP ipv4 `connect` syscalls like this one of me pushing the repo to
github:

```json
{"proctree": [[15808, "/usr/bin/ssh git@github.com git-receive-pack 'oholiab/pidtree-bcc'", "oholiab"], [15807, "git push origin master", "oholiab"], [31438, "-zsh", "oholiab"], [696, "tmux", "oholiab"], [1, "/usr/lib/systemd/systemd --system --deserialize 32", "root"]], "daddr": "140.82.118.4", "pid": 15808, "port": 22, "error": ""}
```

Notably you'll not see any (in theory) for the 127/8, 169.254/16, 10/8 or
172.16/12 ranges because of the subnet filters I've included in the
`example_config.yaml` eBPF program.  This is obviously not an exhaustive list of
loopback or RFC1918 addresses, so you can use the example configuration to write
your own.

Additionally, you can include config like:

```yaml
ports:
  - 22
  - 443
  - 80
```

To see *only* events for these ports.
