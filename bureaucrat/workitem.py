from __future__ import absolute_import

import logging
import json

LOG = logging.getLogger(__name__)

class WorkitemError(Exception):
    """Workitem error."""


class Workitem(object):
    """Work item."""

    mime_type = 'application/x-bureaucrat-workitem'

    def __init__(self, fields=None):
        """Work item constructor."""

        if fields is None:
            fields = {}

        self._fields = fields

        self._header = {
            "message": None,
            "origin": None,
            "target": None
        }

    def __repr__(self):
        """Return instance representation string."""
        return "<Workitem[msg=%(message)s, origin=%(origin)s, target=%(target)s]>" % self._header

    @classmethod
    def loads(cls, blob):
        """Load workitem from JSON formatted string."""
        try:
            delivery = json.loads(blob)
            assert delivery["header"]["message"] is not None
            assert delivery["header"]["origin"] is not None
            assert delivery["header"]["target"] is not None
            assert delivery["fields"] is not None
            self = cls(delivery["fields"])
            self._header = delivery["header"]
            LOG.debug("loaded %r", self)
            return self
        except (ValueError, KeyError, TypeError, AssertionError):
            raise WorkitemError("Can't parse workitem")

    def dumps(self):
        return json.dumps({
            "header": self._header,
            "fields": self._fields
        })

    @property
    def origin(self):
        """Return flow expression ID this workitem originates from."""

        return self._header["origin"]

    @property
    def target(self):
        """Return flow expression ID this workitem targets to."""

        return self._header["target"]

    @property
    def target_pid(self):
        """Return target process ID."""
        return self._header["target"].split('_', 1)[0]

    @property
    def fields(self):
        """Return workitem's fields accessible by workers."""

        return self._fields

    @property
    def name(self):
        """Return workitem's message name."""

        return self._header["message"]

