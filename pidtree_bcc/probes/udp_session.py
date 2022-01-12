import time
import traceback
from collections import namedtuple
from threading import Lock
from typing import Any
from typing import Union

from pidtree_bcc.probes import BPFProbe
from pidtree_bcc.utils import crawl_process_tree
from pidtree_bcc.utils import int_to_ip
from pidtree_bcc.utils import ip_to_int
from pidtree_bcc.utils import never_crash


SessionEventWrapper = namedtuple('SessionEndEvent', ('type', 'sock_pointer'))


class UDPSessionProbe(BPFProbe):

    CONFIG_DEFAULTS = {
        'ip_to_int': ip_to_int,
        'filters': [],
        'includeports': [],
        'excludeports': [],
    }
    USES_DYNAMIC_FILTERS = True
    SESSION_MAX_DURATION_DEFAULT = 120
    SESSION_START = 1
    SESSION_CONTINUE = 2
    SESSION_END = 3

    def build_probe_config(self, probe_config: dict, hotswap_only: bool = False) -> dict:
        config = super().build_probe_config(probe_config, hotswap_only=hotswap_only)
        if not hotswap_only:
            self.session_tracking = {}
            self.thread_lock = Lock()
            self.SIDECARS.append((
                self._session_expiration_worker,
                (config.get('session_max_duration', self.SESSION_MAX_DURATION_DEFAULT),),
            ))
        return config

    def enrich_event(self, event: Any) -> Union[dict, None]:
        """ Parses UDP session event and adds process tree data

        :param Any event: BPF event
        :return: event dictionary with process tree at session end
        """
        with self.thread_lock:
            return self._enrich_event_impl(event)

    def _enrich_event_impl(self, event: Any) -> Union[dict, None]:
        """ Actual `enrich_event` implementation, separated for cleaner thread locking code """
        now = time.monotonic()
        sock_key = event.sock_pointer
        if event.type == self.SESSION_START:
            try:
                error = ''
                proctree = crawl_process_tree(event.pid)
            except Exception:
                error = traceback.format_exc()
                proctree = []
            self.session_tracking[sock_key] = {
                'pid': event.pid,
                'proctree': proctree,
                'destinations': {(event.daddr, event.dport): [now, 1]},
                'error': error,
                'last_update': now,
            }
        elif sock_key in self.session_tracking:
            if event.type == self.SESSION_CONTINUE:
                dest_key = (event.daddr, event.dport)
                session_data = self.session_tracking[sock_key]
                if dest_key not in session_data['destinations']:
                    session_data['destinations'][dest_key] = [now, 1]
                else:
                    session_data['destinations'][dest_key][1] += 1
                session_data['last_update'] = now
            else:
                session_data = self.session_tracking.pop(sock_key)
                session_data.pop('last_update')
                session_data['destinations'] = [
                    {
                        'daddr': int_to_ip(addr_port[0]),
                        'port': addr_port[1],
                        'duration': now - begin_count[0],
                        'msg_count': begin_count[1],
                    }
                    for addr_port, begin_count in session_data['destinations'].items()
                ]
                return session_data

    @never_crash
    def _session_expiration_worker(self, session_max_duration: int):
        """ Handler function for session expiration thread.
        Removes from tracking sessions older than the specified max duration

        :param int session_max_duration: max session duration in seconds
        """
        while True:
            time.sleep(session_max_duration)
            expired = []
            now = time.monotonic()
            with self.thread_lock:
                for sock_pointer, session_data in self.session_tracking.items():
                    if now - session_data['last_update'] > session_max_duration:
                        session_data['error'] = 'session_max_duration_exceeded'
                        expired.append(sock_pointer)
            for sock_pointer in expired:
                end_event = SessionEventWrapper(self.SESSION_END, sock_pointer)
                self._process_events(None, end_event, None, False)
