# pidtree-bcc
> bcc script for tracing process tree ancestry for connect syscalls

# What
`pidtree-bcc` utilizes the [bcc toolchain](https://github.com/iovisor/bcc) to create kprobes for (currently only) tcpv4 connect syscalls, and tracing the ancestry of the process that made the syscall.

It also aims to have a limited set of in-kernel filtering features in order to prevent excessive logging for things like loopback and RFC1918 `connect`s

# Why
Security monitoring purposes. ML based products like Amazon's GuardDuty will tell you when hosts in your infrastructure have made "anomolous" outbound requests, but often these are as-intended but not known about by the team investigating the network traffic. Because of the transient nature of processes, often any useful context is lost by the time investigation can occur.

`pidtree-bcc` is a proof of concept which utilzes the eBPF kernel subsystem to notify a userland daemon of all events so that they can be traced. It enables engineers to quickly identify familiar process trees (for instance, a familiar service name which corresponds to domain names associated with the destination IP address) or another engineer as the originator of request via the username associated with the process.

# Caveats
1. This is only a proof of concept as bcc requires LLVM to be installed on the system that it's invoked on as it compiles to eBPF bytecode at runtime. Having C compilers on target systems that don't need them is not desirable for security reasons. Other eBPF toolchains exist here but this was the easiest way to get started.
2. The current implementation is only for TCP and ipv4.
3. The userland daemon is likely susceptible to interference or denial of service, however the main aim of the project is to reduce the MTTR for "business as usual" events - that is to make so engineers spend less time chasing events that were not actually suspicious
4. Speaking of suspicious, I'm pretty sure my subnet masking methodology is bad and that I should feel bad, but I wanted to ensure that the demo was performant and I never write C :P
