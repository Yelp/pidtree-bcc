# About
`pidtree-bcc` is a framework for creating userland-generated attestation logging
of calling process trees for events that are registered in the kernel (don't
worry it will all become clear!). It is built on top of
[iovisor/bcc](https://github.com/iovisor/bcc), a python framework for hooking
into the Linux eBPF subsystem.

## What is eBPF
eBPF stands for Extended Berkely Packet Filter. As the name suggests, it is an
extended version of the in-kernel virtual machine that the BSDs use for
filtering packets. As the name does not suggest, Linux uses it for in-kernel
tracing.

The eBPF virtual machine places certain restrictions on the type of
program it can run - most notably that loops are not allowed, to prevent
kernel deadlocks. As such, external C functions from included libraries
are not allowed, but header files can be included which is helpful for
using defined data structures and macros.

## What does pidtree-bcc use this for?
`pidtree-bcc` templates out C programs that are compiled at runtime by LLVM into
eBPF bytecode to run in the kernel. It's primary function at the time of writing
is to create kprobes (kernel probes) which will trigger the associated C
function to run whenever the named syscall is dispatched.

Our primary use case is the `tcp_v4_connect` syscall. When one of these fires,
we trigger a C function that checks whether the target IP address is outside of
the local network (i.e. is it non-RFC-1918). If it's internet routeable, a
message is dispatched to the listening python process in userland, containing
details about the parameters of the syscall and the PID of the calling process.
The userland daemon then crawls the process tree from that PID up to PID 1
(init) and logs the lot. This is especially useful for finding false-positives
in IDS logging like Amazon GuardDuty.

By filtering in-kernel without a heavy stack of dependency code, we can create
low-resource, lightning fast filtered events and hand off to userland for any
deep introspection in more lenient languages. The tradeoff here is having to do
things like write bitwise subnet filters due to inclusion restrictions.

It is not tamper-proof due to the userland daemon, but it is fairly reliable in
theory and especially useful for finding false positives and getting a baseline
for outbound traffic which should be low in an internat facing production web
environment.
