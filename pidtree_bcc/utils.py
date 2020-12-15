import functools
import importlib
import inspect
import logging
import os
import socket
import struct
import sys
from typing import Callable
from typing import List
from typing import TextIO
from typing import Type
from typing import Union

import psutil


def crawl_process_tree(pid: int) -> List[dict]:
    """ Takes a process and returns all process ancestry until the ppid is 0

    :param int pid: child process ID
    :return: yields dicts with pid, cmdline and username navigating up the tree
    """
    result = []
    while True:
        if pid == 0:
            break
        proc = psutil.Process(pid)
        result.append(
            {
                'pid': proc.pid,
                'cmdline': ' '.join(proc.cmdline()),
                'username': proc.username(),
            },
        )
        pid = proc.ppid()
    return result


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


def find_subclass(module_path: Union[str, List[str]], base_class: Type) -> Type:
    """ Get child class from module

    :param Union[str, List[str]] module_path: module path or list of paths in dot-notation
    :param Type base_class: class the child class inherits from
    :return: imported child class
    :raise ImportError: module path not valid
    :raise StopIteration: no class found
    """
    if isinstance(module_path, str):
        module_path = [module_path]
    errors = ''
    module = None
    for path in module_path:
        try:
            module = importlib.import_module(path)
            break
        except ImportError as e:
            errors += '\n' + str(e)
    if module is None:
        raise ImportError(
            'Unable to load any module from {}: {}'
            .format(module_path, errors),
        )
    return next(
        obj for _, obj in inspect.getmembers(module)
        if inspect.isclass(obj)
        and issubclass(obj, base_class)
        and obj != base_class
    )


def ip_to_int(network: str) -> int:
    """ Takes an IP and returns the unsigned integer encoding of the address

    :param str network: ip address
    :return: unsigned integer encoding
    """
    return struct.unpack('=L', socket.inet_aton(network))[0]


def int_to_ip(encoded_ip: int) -> str:
    """ Takes IP in interger representation and makes it human readable

    :param int encoded_ip: integer encoded IP
    :return: dot-notation IP
    """
    return socket.inet_ntoa(struct.pack('<L', encoded_ip))


def never_crash(func: Callable) -> Callable:
    """ Decorator for Thread targets which ensures the thread keeps
    running by chatching any exception.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        while True:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logging.error('Error executing {}: {}'.format(func.__name__, e))
    return wrapper


def get_network_namespace(pid: int = None) -> int:
    """ Get network namespace identifier

    :param int pid: process ID (if not provided selects calling process)
    :return: network namespace inum
    """
    if not pid:
        pid = 'self'
    try:
        ns_link = str(os.readlink('/proc/{}/ns/net'.format(pid)))
        # format will be "net:[<inum>]"
        return int(ns_link.strip()[5:-1])
    except Exception:
        return None
