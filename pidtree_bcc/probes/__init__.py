import inspect
import json
import re
from multiprocessing import SimpleQueue
from typing import Any

from bcc import BPF
from jinja2 import Template

from pidtree_bcc.plugins import load_plugins


class BPFProbe:
    """ Base class for defining BPF probes.

    Takes care of loading a BPF program and polling events.
    The BPF program can be either define in the `BPF_TEXT` class variable or
    in a Jinja template file (.j2) with the same basename of the module file.
    In either case the program text will be processed in Jinja templating.
    """

    def __init__(self, output_queue: SimpleQueue, probe_config: dict = {}):
        """ Constructor

        :param Queue output_queue: queue for event output
        :param dict probe_config: (optional) config passed as kwargs to BPF template
                                  all fields are passed to the template engine with the exception
                                  of "plugins". This behaviour can be overidden with the TEMPLATE_VARS
                                  class variable defining a list of config fields.
        """
        self.output_queue = output_queue
        self.plugins = load_plugins(probe_config.get('plugins', {}))
        if not hasattr(self, 'BPF_TEXT'):
            module_src = inspect.getsourcefile(type(self))
            with open(re.sub(r'\.py$', '.j2', module_src)) as f:
                self.BPF_TEXT = f.read()
        if hasattr(self, 'TEMPLATE_VARS'):
            template_config = {k: probe_config[k] for k in self.TEMPLATE_VARS}
        else:
            template_config = probe_config.copy()
            template_config.pop('plugins', None)
        self.expanded_bpf_text = Template(self.BPF_TEXT).render(**template_config)

    def _process_events(self, cpu: Any, data: Any, size: Any):
        """ BPF event callback

        :param Any cpu: unused arg required for callback
        :param Any data: BPF raw event
        :param Any size: unused arg required for callback
        """
        event = self.bpf['events'].event(data)
        event = self.enrich_event(event)
        for event_plugin in self.plugins:
            event = event_plugin.process(event)
        self.output_queue.put(json.dumps(event))

    def start_polling(self):
        """ Start infinite loop polling BPF events """
        self.bpf = BPF(text=self.expanded_bpf_text)
        self.bpf['events'].open_perf_buffer(self._process_events)
        while True:
            self.bpf.perf_buffer_poll()

    def enrich_event(self, event: Any) -> dict:
        """ Transform raw BPF event data into dictionary,
        possibly adding more interesting data to it.

        :param Any event: BPF event data
        """
        raise NotImplementedError
