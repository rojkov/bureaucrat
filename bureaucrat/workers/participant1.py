import logging
import json

from taskqueue.worker import BaseWorker

LOG = logging.getLogger(__name__)

class Worker(BaseWorker):

    def handle_task(self, workitem):
        LOG.debug("Workitem: %r" % workitem)
        workitem._body["type"] = "response" # TODO: disgusting!
        return workitem

