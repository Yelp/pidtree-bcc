import pwd
import sys
from typing import Tuple

from pidtree_bcc.plugins import BasePlugin


class LoginuidMap(BasePlugin):
    """ Plugin for mapping PID to loginuid and username """

    NO_LOGINUID = 4294967295  # unsigned -1

    def process(self, event: dict) -> dict:
        """ Adds loginuid info on process tree """
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
            sys.stderr.write('Error fetching loginuid: {}'.format(e))
        return None, None
