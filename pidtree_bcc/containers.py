import enum
import fnmatch
import json
import logging
import os
import shlex
import subprocess
import time
from functools import lru_cache
from itertools import chain
from typing import Callable
from typing import Generator
from typing import Iterable
from typing import List
from typing import NamedTuple
from typing import Set
from typing import Tuple


class ContainerEventType(enum.Enum):
    start = 'start'
    stop = 'stop'


class ContainerEvent(NamedTuple):
    event_type: ContainerEventType
    container_id: str

    def __bool__(self) -> bool:
        return bool(self.container_id)


class MountNSInfo(NamedTuple):
    container_id: str
    container_name: str
    ns_id: int
    event_type: ContainerEventType = ContainerEventType.start


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


def extract_container_name(inspect_data: dict) -> str:
    """ Extracts name from container information, falling back to labels if needed.
    This is needed because the "Name" field is basically always empty for containerd.

    :param dict inspect_data: container information
    :return: container name
    """
    name = inspect_data.get('Name', '').lstrip('/')
    return (
        name
        if name
        else inspect_data.get('Config', {}).get('Labels', {}).get('io.kubernetes.pod.name', '')
    )


@lru_cache(maxsize=2048)
def inspect_container(sha: str) -> dict:
    """ Inspect container

    :param str sha: container hash ID
    :return: inspect data
    """
    output = subprocess.check_output(
        (detect_containerizer_client(), 'inspect', sha),
        encoding='utf8',
    )
    return json.loads(output)[0]


@lru_cache(maxsize=20000)
def get_container_mntns_id(sha: str, second_try: bool = False) -> int:
    """ Get mount namespace ID for a container

    :param str sha: container hash ID
    :return: mount namespace ID
    """
    try:
        inspect_data = inspect_container(sha)
        main_pid = inspect_data['State']['Pid']
        if main_pid == 0 and not second_try:
            # when detecting containers from the events stream, we may be
            # "too fast" and there is no process associated to the container yet
            time.sleep(0.5)
            return get_container_mntns_id(sha, second_try=True)
    except Exception as e:
        logging.error(f'Issue inspecting container {sha}: {e}')
        return -1
    try:
        return os.stat(f'/proc/{main_pid}/ns/mnt').st_ino
    except Exception as e:
        logging.error(f'Issue reading mntns ID for {main_pid}: {e}')
    return -1


def filter_containers_with_label_patterns(
    container_ids: Iterable[str],
    patterns: Iterable[str],
) -> List[Tuple[str, str]]:
    """ Given a list of container IDs, find the ones with labels matching any of the patterns

    :param Iterable[str] container_ids: collection of container IDs
    :param Iterable[str] patterns: collection of label patterns, with entries in the format `<label_name>=<pattern>,...`
    :return: filtered list of container IDs
    """
    result = []
    unpacked_patterns = [
        [pattern.split('=', 1) for pattern in pattern_set.split(',')]
        for pattern_set in patterns
    ]
    for container_id in container_ids:
        try:
            container_info = inspect_container(container_id)
            labels = container_info.get('Config', {}).get('Labels', {})
            if labels and any(
                all(
                    label_key in labels
                    and fnmatch.fnmatch(labels[label_key], pattern)
                    for label_key, pattern in pattern_set
                )
                for pattern_set in unpacked_patterns
            ):
                result.append((container_id, extract_container_name(container_info)))
        except Exception as e:
            logging.error(f'Issue inspecting container {container_id}: {e}')
    return result


def list_container_mnt_namespaces(
    patterns: Iterable[str] = None,
    generator: Callable[[], List[str]] = list_containers,
) -> Set[MountNSInfo]:
    """ Get collection of mount namespace IDs for running containers matching label filters

    :param Iterable[str] filter_labels: list of label values, `<label_name>=<pattern>,...`
    :param Callable[[], List[str]] generator: method to call to generate container ID list
    :return: set of mount namespace info
    """
    patterns = patterns if patterns else []
    return {
        mntns_info
        for mntns_info in (
            MountNSInfo(container_id, name, get_container_mntns_id(container_id))
            for container_id, name in filter_containers_with_label_patterns(generator(), patterns)
            if container_id
        )
        if mntns_info.ns_id > 0
    }


def monitor_container_mnt_namespaces(patterns: Iterable[str] = None) -> Generator[MountNSInfo, None, None]:
    """ Listens to containerizer events for new containers being created, and grab their namespace info

    :param Iterable[str] filter_labels: list of label values, `<label_name>=<pattern>,...`
    :return: set of mount namespace info
    """
    for event in monitor_container_events():
        if event.event_type == ContainerEventType.start:
            yield from list_container_mnt_namespaces(patterns, lambda: [event.container_id])
        else:
            yield MountNSInfo(event.container_id, '', 0, event.event_type)


def _tail_subprocess_json(cmd: str, shell: bool = False) -> Generator[dict, None, None]:
    """ Run command and tail output line by line, parsing it as JSON

    :param Iterable[str] cmd: command to run
    :return: yield dicts, stops on errors
    """
    try:
        with subprocess.Popen(
            args=cmd if shell else shlex.split(cmd),
            stdout=subprocess.PIPE,
            encoding='utf-8',
            shell=shell,
        ) as proc:
            for line in proc.stdout:
                if not line.strip():
                    continue
                yield json.loads(line)
    except Exception as e:
        logging.error(f'Error while running {cmd}: {e}')


def monitor_container_events() -> Generator[ContainerEvent, None, None]:
    """ Listens to containerizer events for new containers being created

    :return: yields container IDs
    """
    client_cli = detect_containerizer_client()
    if client_cli == 'docker':
        use_shell = False
        event_filters = '--filter type=container --filter event=start --filter event=die'

        def event_extractor(event): return ContainerEvent(
            ContainerEventType.start if event.get('status', '') == 'start' else ContainerEventType.stop,
            event.get('id', ''),
        )
    else:
        use_shell = True
        event_filters = "| grep -E '/tasks/(start|delete)'"

        def event_extractor(event): return ContainerEvent(
            ContainerEventType.start if event.get('Topic', '').endswith('start') else ContainerEventType.stop,
            event.get('ID', ''),
        )

    cmd = f"{client_cli} events --format '{{{{json .}}}}' {event_filters}"
    while True:
        event_gen = _tail_subprocess_json(cmd, use_shell)
        for event in event_gen:
            res = event_extractor(event)
            if not res:
                continue
            yield res
