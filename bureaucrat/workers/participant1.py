import logging
import json

from taskqueue.worker import BaseWorker

LOG = logging.getLogger(__name__)

class Worker(BaseWorker):

    def handle_task(self, workitem):
        LOG.debug("Workitem: %r" % workitem)
        wtype, body = workitem.dumps().split(" ", 1)
        LOG.debug("Body: %s" % body)
        wi = json.loads(body)
        wi["type"] = "response"
        workitem.loads("%s %s" % (wtype, json.dumps(wi)))
        return workitem

