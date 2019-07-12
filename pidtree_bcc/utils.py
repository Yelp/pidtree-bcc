import psutil
import contextlib
import sys

def crawl_process_tree(proc):
    """ Takes a process and returns all process ancestry until the ppid is 0 """
    procs = [proc]
    while True:
        ppid = procs[len(procs)-1].ppid()
        if ppid == 0:
            break
        procs.append(psutil.Process(ppid))
    return procs

@contextlib.contextmanager
def smart_open(filename=None, mode='r'):
    """ Contextmanager for file OR stdout open, shamelessly cribbed from https://stackoverflow.com/questions/17602878/how-to-handle-both-with-open-and-sys-stdout-nicely """
    if filename and filename != '-':
        fh = open(filename, mode)
    else:
        fh = sys.stdout
    try:
        yield fh
    finally:
        if fh is not sys.stdout:
            fh.close()
