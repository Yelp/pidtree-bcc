import logging
import pwd
from typing import Tuple

from pidtree_bcc.plugins import BasePlugin


class LoginuidMap(BasePlugin):
    """ Plugin for mapping PID to loginuid and username """

    NO_LOGINUID = 4294967295  # unsigned -1

    def __init__(self, args: dict):
        super().__init__(args)
        self.process = (
            self._process_tl
            if args.get('top_level', False)
            else self._process_pt
        )

    def _process_tl(self, event: dict) -> dict:
        """ Adds loginuid info for the child process """
        loginuid, username = self._get_loginuid(event['pid'])
        if loginuid is not None:
            event['loginuid'] = loginuid
            event['loginname'] = username
        return event

    def _process_pt(self, event: dict) -> dict:
        """ Adds loginuid info to the process tree """
        for proc in event['proctree']:  # proctree is sorted from leaf to root
            if proc['pid'] == 1:
                break
            loginuid, username = self._get_loginuid(proc['pid'])
            if loginuid is not None:
                proc['loginuid'] = loginuid
                proc['loginname'] = username
        return event

    @staticmethod
    def _get_loginuid(pid: int) -> Tuple[int, str]:
        """ Given a PID get loginuid and corresponding username

        :param int pid: process ID:
        :return: loginuid and username
        """
        try:
            with open('/proc/{}/loginuid'.format(pid)) as f:
                loginuid = int(f.read().strip())
            if loginuid == LoginuidMap.NO_LOGINUID:
                return None, None
            return loginuid, pwd.getpwuid(loginuid).pw_name
        except Exception as e:
            logging.error('Error fetching loginuid: {}'.format(e))
        return None, None
