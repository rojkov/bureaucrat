import logging
import json

from taskqueue.worker import BaseWorker

LOG = logging.getLogger(__name__)

process_def = """<?xml version="1.0"?>
<process>
    <action participant="participant2" />
</process>
"""

class Worker(BaseWorker):

    def handle_task(self, workitem):
        LOG.debug("Workitem: %r" % workitem)
        if "counter" not in workitem.fields:
            workitem.fields["counter"] = 0
        else:
            workitem.fields["counter"] += 1
        workitem.fields["some_process"] = process_def
        return workitem

