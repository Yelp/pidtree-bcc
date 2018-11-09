import sys
import argparse
from bcc import BPF
import json
import yaml
import psutil
import os
import socket
import struct

bpf_text = """
#include <net/sock.h>
#include <bcc/proto.h>

#define first_n_octets(n, ip) (ip<<(n*8))>>(n*8)
#define first_two_octets_192_168 0xa8c0
#define first_octet_10 0xa
#define first_octet_127 0x7f

BPF_HASH(currsock, u32, struct sock *);

int kprobe__tcp_v4_connect(struct pt_regs *ctx, struct sock *sk)
{
    u32 pid = bpf_get_current_pid_tgid();
    currsock.update(&pid, &sk);
    return 0;
};

int kretprobe__tcp_v4_connect(struct pt_regs *ctx)
{
    int ret = PT_REGS_RC(ctx);
    u32 pid = bpf_get_current_pid_tgid();

    struct sock **skpp;
    skpp = currsock.lookup(&pid);
    if (skpp == 0) return 0; // not there!
    if (ret != 0) {
        // failed to sync
        currsock.delete(&pid);
        return 0;
    }
    
    struct sock *skp = *skpp;
    u32 saddr = 0, daddr = 0;
    u16 dport = 0;
    bpf_probe_read(&daddr, sizeof(daddr), &skp->__sk_common.skc_daddr);
    // Nasty hack to not match 192.168 networks
    u8 first_octet = first_n_octets(1, daddr);
    u16 first_two_octets = first_n_octets(2, daddr);
    if (first_octet == first_octet_10
         || first_octet == first_octet_127
         || first_two_octets == first_two_octets_192_168) {
        currsock.delete(&pid);
        return 0;
    }

    bpf_probe_read(&saddr, sizeof(saddr), &skp->__sk_common.skc_rcv_saddr);
    bpf_probe_read(&dport, sizeof(dport), &skp->__sk_common.skc_dport);

    bpf_trace_printk("{\\"pid\\": %d, \\"daddr\\": \\"%x\\", \\"dport\\": %d}\\n",
                     pid, daddr, ntohs(dport));
    
    currsock.delete(&pid);

    return 0;
}
"""

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", type=str, help="yaml file containing subnet safelist information")
    args = parser.parse_args()
    if args.config is not None and not os.path.exists(args.config):
        os.stderr.write("--config file does not exist")
    return(args)

def crawl_process_tree(proc):
    procs = [proc]
    while True:
        ppid = procs[len(procs)-1].ppid()
        if ppid == 0:
            break
        procs.append(psutil.Process(ppid))
    return procs
    
def main(args):
    global bpf_text
    b = BPF(text=bpf_text)
    while True:
        trace = b.trace_readline()
        json_event = trace.split(":", 2)[2:][0]
        event = json.loads(json_event)
        proc = None
        proctree = []
        error = ""
        try:
            proc = psutil.Process(event["pid"])
            proctree = crawl_process_tree(proc)
        except Exception as e:
            error=str(e)
        print(json.dumps(
            {"pid": event["pid"],
             "proctree": list(((p.pid, " ".join(p.cmdline()), p.username()) for p in proctree)),
             "daddr": socket.inet_ntoa(struct.pack('<L', int(event["daddr"], 16))),
             "port": event["dport"],
             "error": error}))
    sys.exit(0)

if __name__ == "__main__":
    main(parse_args())
