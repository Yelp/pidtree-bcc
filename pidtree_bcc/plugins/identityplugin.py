from pidtree_bcc.plugin import BasePlugin


class Identityplugin(BasePlugin):
    """ Example plugin not performing any event modification """

    def process(self, event: dict) -> dict:
        return event
