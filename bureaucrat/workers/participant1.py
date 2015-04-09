import logging
import json

from taskqueue.worker import BaseWorker

LOG = logging.getLogger(__name__)

class Worker(BaseWorker):

    def handle_task(self, workitem):
        LOG.debug("Workitem: %r" % workitem)
        if "counter" not in workitem.fields:
            workitem.fields["counter"] = 0
        else:
            workitem.fields["counter"] += 1
        return workitem

