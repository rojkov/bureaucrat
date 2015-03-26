import logging
import json

from taskqueue.workitem import Workitem as BaseWorkitem
from taskqueue.workitem import WorkitemError as BaseWorkitemError

LOG = logging.getLogger(__name__)

class WorkitemError(BaseWorkitemError):
    pass

class Workitem(BaseWorkitem):
    """Workitem specific to Bureaucrat."""

    def loads(self, blob):
        try:
            self._body = json.loads(blob)
            self.worker_type = self._body["participant"]
            self._process_id = self._body["process_id"]
            self._activity_id = self._body["activity_id"]
        except (ValueError, KeyError, TypeError):
            raise WorkitemError("Can't parse workitem body")

    def dumps(self):
        if self._body is None:
            raise WorkitemError("Workitem hasn't been loaded")
        return json.dumps(self._body)

    def set_error(self, error):
        self._body["error"] = error

    def set_trace(self, trace):
        self._body["trace"] = trace

    @property
    def process_id(self):
        """Return process Id this workitem belongs to.

        This is a read only property.
        """

        if self._body is None:
            raise WorkitemError("Workitem hasn't been loaded")
        return self._process_id

    @property
    def activity_id(self):
        """Return activity Id this workitem originates from.

        This is a read only property.
        """

        if self._body is None:
            raise WorkitemError("Workitem hasn't been loaded")
        return self._activity_id
