import logging

from taskqueue.worker import BaseWorker

LOG = logging.getLogger(__name__)

PROCESS_DEF = """<?xml version="1.0"?>
<process>
    <action participant="participant2" />
</process>
"""

class Worker(BaseWorker):

    def handle_task(self, workitem):
        LOG.debug("Workitem: %r", workitem)
        if "counter" not in workitem._payload:
            workitem._payload["counter"] = 0
        else:
            workitem._payload["counter"] += 1
        workitem._payload["some_process"] = PROCESS_DEF
        return workitem

