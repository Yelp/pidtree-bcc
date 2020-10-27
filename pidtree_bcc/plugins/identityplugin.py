from pidtree_bcc.plugins import BasePlugin


class Identityplugin(BasePlugin):
    """ Example plugin not performing any event modification """

    PROBE_SUPPORT = '*'

    def process(self, event: dict) -> dict:
        return event
