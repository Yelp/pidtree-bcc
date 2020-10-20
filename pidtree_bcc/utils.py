import importlib
import inspect
import sys
from typing import List
from typing import TextIO
from typing import Type

import psutil


def crawl_process_tree(proc: psutil.Process) -> List[psutil.Process]:
    """ Takes a process and returns all process ancestry until the ppid is 0

    :param psutil.Process proc: child process
    :return: process tree as a list
    """
    procs = [proc]
    while True:
        ppid = procs[len(procs)-1].ppid()
        if ppid == 0:
            break
        procs.append(psutil.Process(ppid))
    return procs


def smart_open(filename: str = None, mode: str = 'r') -> TextIO:
    """ File OR stdout open

    :param str filename: filename
    :param str mode: file opening mode
    :return: file handle object
    """
    if filename and filename != '-':
        return open(filename, mode)
    else:
        return sys.stdout


def find_subclass(module_path: str, base_class: Type) -> Type:
    """ Get child class from module

    :param str module_path: module path in dot-notation
    :param Type base_class: class the child class inherits from
    :return: imported child class
    :raise ImportError: module path not valid
    :raise StopIteration: no class found
    """
    module = importlib.import_module(module_path)
    return next(
        obj for _, obj in inspect.getmembers(module)
        if inspect.isclass(obj)
        and issubclass(obj, base_class)
        and obj != base_class
    )
