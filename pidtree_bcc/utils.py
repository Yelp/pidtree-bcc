import importlib
import inspect
import socket
import struct
import sys
from typing import Generator
from typing import TextIO
from typing import Type

import psutil


def crawl_process_tree(pid: int) -> Generator[dict, None, None]:
    """ Takes a process and returns all process ancestry until the ppid is 0

    :param int pid: child process ID
    :return: yields dicts with pid, cmdline and username navigating up the tree
    """
    while True:
        if pid == 0:
            break
        proc = psutil.Process(pid)
        yield {
            'pid': proc.pid,
            'cmdline': ' '.join(proc.cmdline()),
            'username': proc.username(),
        }
        pid = proc.ppid()


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
