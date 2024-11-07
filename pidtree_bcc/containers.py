import logging
import os
import subprocess
from functools import lru_cache
from itertools import chain
from typing import List
from typing import Set


@lru_cache(maxsize=1)
def detect_containerizer_client() -> str:
    """ Detect whether the system is using Docker or Containerd.
    Since containerd does not have a proper python API implementation, we rely on
    CLI tools to query container information in both cases.
    This method is very opinionated towards detecting Containerd usage in Kubernetes,
    so in most cases it will fall back to standard Docker.

    :return: CLI tool to query containerizer
    """
    return 'nerdctl' if os.path.exists('/var/run/containerd/io.containerd.runtime.v2.task/k8s.io') else 'docker'


def list_containers(filter_labels: List[str] = None) -> List[str]:
    """ List running containers matching filter

    :param List[str] filter_labels: list of label values, either `<label_name>` or `<label_name>=<label_value>`
    :return: yields container hash IDs
    """
    filter_args = chain.from_iterable(('--filter', f'label={label}') for label in (filter_labels or []))
    try:
        output = subprocess.check_output(
            (
                detect_containerizer_client(), 'ps',
                '--no-trunc', '--quiet', *filter_args,
            ), encoding='utf8',
        )
        return output.splitlines()
    except Exception as e:
        logging.error(f'Issue listing running containers: {e}')
    return []


@lru_cache(maxsize=2048)
def get_container_mntns_id(sha: str) -> int:
    """ Get mount namespace ID for a container

    :param str sha: container hash ID
    :return: mount namespace ID
    """
    try:
        output = subprocess.check_output(
            (
                detect_containerizer_client(), 'inspect',
                '-f', r'{{.State.Pid}}', sha,
            ), encoding='utf8',
        )
        pid = int(output.splitlines()[0])
    except Exception as e:
        logging.error(f'Issue inspecting container {sha}: {e}')
        return -1
    try:
        return os.stat(f'/proc/{pid}/ns/mnt').st_ino
    except Exception as e:
        logging.error(f'Issue reading mntns ID for {pid}: {e}')
    return -1


def list_container_mnt_namespaces(filter_labels: List[str] = None) -> Set[int]:
    """ Get collection of mount namespace IDs for running containers matching label filters

    :param List[str] filter_labels: list of label values, either `<label_name>` or `<label_name>=<label_value>`
    :return: set of mount namespace IDs
    """
    return {
        mntns_id
        for mntns_id in (
            get_container_mntns_id(container_id)
            for container_id in list_containers(filter_labels)
            if container_id
        )
        if mntns_id > 0
    }
