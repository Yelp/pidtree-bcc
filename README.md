# pidtree-bcc
> bcc script for tracing process tree ancestry for connect syscalls

[![Build Status](https://github.com/Yelp/pidtree-bcc/actions/workflows/test.yml/badge.svg)](https://github.com/Yelp/pidtree-bcc/actions)

## What
`pidtree-bcc` utilizes the [bcc toolchain](https://github.com/iovisor/bcc) to
create kprobes for (currently only) tcpv4 connect syscalls, and tracing the
ancestry of the process that made the syscall.

It also aims to have a tunable set of in-kernel filtering features in order to
prevent excessive logging for things like loopback and RFC1918 `connect`s

## Why
Security monitoring purposes. ML based products like Amazon's GuardDuty will
tell you when hosts in your infrastructure have made "anomalous" outbound
requests, but often these are as-intended but not known about by the team
investigating the network traffic. Because of the transient nature of processes,
often any useful context is lost by the time investigation can occur.

`pidtree-bcc` is a supplementary intrusion detection system which
utilizes the eBPF kernel subsystem to notify a userland daemon of all
events so that they can be traced. It enables engineers to quickly
identify familiar process trees (for instance, a familiar service name
which corresponds to domain names associated with the destination IP
address) or another engineer as the originator of request via the
username associated with the process.

## Features
- Full process tree attestation for outbound IPv4 TCP connections and
  additional process metadata
  - PID `pid`
  - Command-line for process `cmdline`
  - Owner of process `username`
    - Populated with UID when no `/etc/passwd` is mounted
- Connection metadata including
  - Source IP `saddr`
  - Destination IP `daddr`
  - Destination port `port`
- Full process tree attestation for IPv4 TCP/UDP listeners with the
  same process metadata as above and
  - Local bind address `laddr`
  - Listening port `port`
  - Network protocol `protocol` (e.g. tcp)
  - Configurable to also periodically provide snapshots of all listening processes
- Best effort tracking of UDP sessions with configurability and output
  similar to the ones of TCP outbound connections.
- Optional plugin system for enriching events in userland
  - Included `sourceipmap` plugin for mapping source address
  - Included `loginuidmap` plugin for adding loginuid info to process tree

## Caveats
* bcc compiles your eBPF "program" to bytecode at runtime,
  and as such needs the appropriate kernel headers installed on the host.
* The current probe implementations only support IPv4.
* The userland daemon is likely susceptible to interference or denial of
  service, however the main aim of the project is to reduce the MTTR for
  "business as usual" events - that is to make so engineers spend less time
  chasing events that were not actually suspicious
* It's possible to cause a race condition in the userland daemon in that
  the process or parent process that triggers the kprobe may in fact
  exit before the userland daemon tries to inspect it. Setting niceness
  values might help, but it is better to consider loopback addresses to
  be out-of-scope.

## Dependencies
See the installation instructions for [bcc](https://github.com/iovisor/bcc).
It is required for the `python3-bcc` package and its dependencies to be installed.

Most notably, you need a kernel with eBPF enabled (4.4 onward) and the
Linux headers for your running kernel version installed. For a
quick-start, there is a Dockerfile included and a make target (`make
docker-run`) to launch pidtree-bcc. Following the thread here is the
best way to get a full view of the requisite state of the system for
pidtree-bcc to work.

## Probes
Pidtree-bcc implements a modular probe system which allows multiple eBPF programs
to be compiled and run in parallel. Probe loading is handled via the top-level keys
in the configuration (see [`example_config.yml`](example_config.yml) for inline documentation).

Currently, this repository implements the `tcp_connect`, `net_listen` and `udp_session` probes.
It is possible to extend this system with external packages via the `--extra-probe-path`
command line parameter.

## Usage
> CAUTION! The Makefile calls 'docker run' with `--priveleged`,
> `--cap-add=SYS_ADMIN` and `--pid host` so it is your responsibility
> to understand what this means and ensure that it's not going to do
> anything untoward!

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
  "saddr": "X.X.X.X",
  "error": "",
  "port": 6697,
  "probe": "tcp_connect"
}
```

Notably you'll not see any for the 127/8, 169.254/16, 10/8, 192.168/16
or 172.16/12 ranges because of the subnet filters I've included in the
`example_config.yaml` eBPF program.  This is obviously not an exhaustive
list of addresses you might want to filter, so you can use the example
configuration to write your own.

Additionally, you can make the filters apply only to certain ports, using `except_ports` and `include_ports`.
For example:

```yaml
tcp_connect:
  filters:
    - subnet_name: 10
      network: 10.0.0.0
      network_mask: 255.0.0.0
      description: "all RFC 1918 10/8"
      except_ports: [80]
```

Would mean filter out all traffic from 10.0.0.0/8 except for that on port 80. If you changed except_ports
to include_ports, then it would filter out only traffic to 10.0.0.0/8 on port 80.

In addition, you can add a global config for filtering out all traffic except those for specific ports,
using the option `includeports`. There also exists the specular global probe config `excludeports` which
allows to specify a list of ports or port ranges to exclude from event capturing. These parameters are
available for all currently implement probes (`tcp_connect`, `net_listen` and `udp_session`) and are mutually
exclusive. If both are specified for a single probe, `includeports` will have precedence.

## Plugins
Plugin configuration is populated using the `plugins` key at the top level of the probe configuration:

```yaml
probe_x:
  ...
  plugins:
    somepluginname:
      enabled: <True/False> #True by default
      unload_on_init_exception: <True/False> #False by default
      arg_1: "blah"
      arg_2:
        - some
        - values
    arg...
```

See below for a working example

Plugins with no `enabled` argument set will be *enabled by default*

The `unload_on_init_exception` boolean allows you to save pidtree-bcc
from module misconfiguration for any given plugin configuration dict by
simply setting it to `True`. Exceptions will be printed to stderr and
the plugin will not be loaded.

It is possible to extend this system by loading plugins from external
packages via the `--extra-plugin-path` command line parameter.

### Sourceipmap
This plugin adds in a key-value pair to the connection metadata
(top-level) with a configurable key and a value given by mapping the IP
to a name given by a merged series of /etc/hosts format hostfiles. If
there is no corresponding name an empty string is returned.

Configuration is re-read in to memory a minimum of every 2 seconds, so
connections *can* be misattributed.

To enable the `sourceipmap` plugin, simply include a `plugins` stanza in the config like so:

```yaml
...
  plugins:
    sourceipmap:
      enabled: True
      hostfiles:
        - "/etc/array"
        - "/etc/of"
        - "/etc/hostfiles"
      attribute_key: "source_host"
```

If you're looking to map source container names, you might want to try
running `itests/gen-ip-mapping.sh FILENAME INTERVAL` which will populate
`FILENAME` with a map of ips to docker container names ever `INTERVAL`
seconds.

If you then volume mount the *directory* that this file is in (the contents
of the file will not update if you bind mount it in directly) to a location
like `/maps`, you can then use a configuration like:

```yaml
...
  plugins:
    sourceipmap:
      enabled: True
      hostfiles:
        - "/maps/ipmapping.txt"
      attribute_key: "source_container"
```

### LoginuidMap
This plugin adds `loginuid` information (the ID and the corresponding username)
to the logged process data. It can be configured to either populate info just for
the top level event (i.e. the leaf process in the tree) or to iterate over all
tree nodes. The info will be stored in the `loginuid` and `loginname` fields.

```yaml
...
  plugins:
    loginuidmap:
      enabled: True
      top_level: <True/False>
```

## Development caveats
* Plugins must define explicitly the probes they support via the `PROBE_SUPPORT` class
  variable. It is possible to specify the wildcard `*` to state that a plugin is
  compatible with all probes, but that is to be used with care to avoid runtime issues.
* Probes support the concept of "sidecar" threads. Due to the limitations of Python's
  threading implementation, these should only implement lightweight tasks in order to
  avoid "stealing" performance from the main probe process.
* Most of the code is self-documenting, so if something is not clear, try to look in the
  docstrings.
