import pwd
import sys

from pidtree_bcc.plugin import BasePlugin


class Loginuidmap(BasePlugin):
    """ Plugin for mapping PID to loginuid and username """

    NO_LOGINUID = 4294967295  # unsigned -1

    def process(self, event):
        for proc in event['proctree']:
            loginuid, username = self._get_loginuid(proc['pid'])
            if loginuid is not None:
                proc['loginuid'] = loginuid
                proc['loginname'] = username
        return event

    @staticmethod
    def _get_loginuid(pid):
        """ Given a PID get loginuid and corresponding username

        :param int pid: process ID:
        :return: loginuid and username
        """
        try:
            with open('/proc/{}/loginuid'.format(pid)) as f:
                loginuid = int(f.read().strip())
            if loginuid == Loginuidmap.NO_LOGINUID:
                return None, None
            return loginuid, pwd.getpwuid(loginuid).pw_name
        except Exception as e:
            sys.stderr.write('Error fetching loginuid: {}'.format(e))
        return None, None
