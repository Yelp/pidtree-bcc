import psutil
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

def smart_open(filename=None, mode='r'):
    """ File OR stdout open """
    if filename and filename != '-':
        return(open(filename, mode))
    else:
        return(sys.stdout)
