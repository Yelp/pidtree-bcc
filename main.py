import argparse
import contextlib
import json
import os
import psutil
import socket
import struct
import sys
import yaml

from bcc import BPF
from datetime import datetime
from jinja2 import Template


bpf_text = """

#include <net/sock.h>
#include <bcc/proto.h>

// IPs and masks are given in integer notation with their dotted notation in the comment
{% for filter in filters %}
// {{ filter.get("description", filter["subnet_name"]) }}
#define subnet_{{ filter["subnet_name"] }} {{ ip_to_int(filter["network"]) }} // {{ filter["network"] }}
#define subnet_{{ filter["subnet_name"] }}_mask {{ ip_to_int(filter["network_mask"]) }} // {{ filter["network_mask"] }}
{% endfor %}

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
    if (0 // for easier templating 
    {% for filter in filters %}
         || (subnet_{{ filter["subnet_name"] }} & subnet_{{ filter["subnet_name"] }}_mask) == (daddr & subnet_{{ filter["subnet_name"] }}_mask)
    {% endfor %}) {
        currsock.delete(&pid);
        return 0;
    }
    bpf_probe_read(&dport, sizeof(dport), &skp->__sk_common.skc_dport);
    {% if includeports != []: %}
    if ( 1 
    {% for port in includeports %}
        && ntohs({{ port }}) != dport 
    {% endfor %}) {
        currsock.delete(&pid);
        return 0;
    }
    {% endif %}

    bpf_probe_read(&saddr, sizeof(saddr), &skp->__sk_common.skc_rcv_saddr);

    bpf_trace_printk("{\\"pid\\": %d, \\"daddr\\": \\"%x\\", \\"dport\\": %d}\\n",
                     pid, daddr, ntohs(dport));
    
    currsock.delete(&pid);

    return 0;
}
"""

def parse_args():
    """ Parses args """
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", type=str, help="yaml file containing subnet safelist information")
    parser.add_argument("-p", "--print-and-quit", action='store_true', default=False, help="don't run, just print the eBPF program to be compiled and quit")
    parser.add_argument("-f", "--output_file", type=str, default='-', help="File to output to (default is STDOUT, denoted by -)")
    args = parser.parse_args()
    if args.config is not None and not os.path.exists(args.config):
        os.stderr.write("--config file does not exist")
    return(args)

def parse_config(config_file):
    """ Parses yaml file at path `config_file` """
    if config_file is None:
        return {}
    return yaml.load(open(config_file, 'r').read())

@contextlib.contextmanager
def smart_open(filename=None):
    """ Contextmanager for file OR stdout open, shamelessly cribbed from https://stackoverflow.com/questions/17602878/how-to-handle-both-with-open-and-sys-stdout-nicely """
    if filename and filename != '-':
        fh = open(filename, 'w')
    else:
        fh = sys.stdout
    try:
        yield fh
    finally:
        if fh is not sys.stdout:
            fh.close()

def ip_to_int(network):
    """ Takes an IP and returns the unsigned integer encoding of the address """
    return struct.unpack('=L', socket.inet_aton(network))[0]
    
def crawl_process_tree(proc):
    """ Takes a process and returns all process ancestry until the ppid is 0 """
    procs = [proc]
    while True:
        ppid = procs[len(procs)-1].ppid()
        if ppid == 0:
            break
        procs.append(psutil.Process(ppid))
    return procs
    
def main(args):
    config = parse_config(args.config)
    global bpf_text
    expanded_bpf_text = Template(bpf_text).render(
        ip_to_int=ip_to_int,
        filters=config.get("filters", []),
        includeports=config.get("includeports", []),
    )
    if args.print_and_quit:
        print(expanded_bpf_text)
        sys.exit(0)
    b = BPF(text=expanded_bpf_text)
    with smart_open(args.output_file) as out:
        while True:
            trace = b.trace_readline()
            # print(trace)
            proctree_enriched = []
            error = ""
            try:
                # FIXME: this next line isn't right - sometimes there are more colons
                json_event = trace.split(":", 2)[2:][0]
                event = json.loads(json_event)
                proc = psutil.Process(event["pid"])
                proctree = crawl_process_tree(proc)
                proctree_enriched = list({"pid": p.pid, "cmdline": " ".join(p.cmdline()), "username":  p.username()} for p in proctree)
            except Exception as e:
                error=str(e)
            print >> out, json.dumps(
                {"timestamp": datetime.utcnow().isoformat() + 'Z',
                 "pid": event["pid"],
                 "proctree": proctree_enriched,
                 "daddr": socket.inet_ntoa(struct.pack('<L', int(event["daddr"], 16))),
                 "port": event["dport"],
                 "error": error})
            out.flush()
    sys.exit(0)

if __name__ == "__main__":
    main(parse_args())
