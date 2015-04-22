from __future__ import absolute_import

import logging
import time
import json
import os
import os.path

from bureaucrat.workitem import Workitem
from bureaucrat.storage import Storage
from bureaucrat.storage import lock_storage

LOG = logging.getLogger(__name__)

class Schedule(object):
    """Implements scheduled events."""

    def __init__(self, channel):
        """Initialize instance."""

        self.channel = channel

    @lock_storage
    def register(self, code, instant, target, context):
        """Register new schedule."""
        LOG.debug("Register '%s' for %s at %d", code, target, instant)

        assert type(instant) is int

        schedules = []
        storage = Storage.instance()
        if storage.exists("schedule", str(instant)):
            schedules = json.loads(storage.load("schedule", str(instant)))
        schedules.append({
            "code": code,
            "target": target,
            "context": context
        })
        storage.save("schedule", str(instant), json.dumps(schedules))

    @lock_storage
    def handle_alarm(self):
        """Load schedule."""

        LOG.debug("Handling alarm")
        timestamp = int(time.time())
        storage = Storage.instance()
        for key in storage.keys("schedule"):
            if timestamp >= int(key):
                schedules = json.loads(storage.load("schedule", key))
                for sch in schedules:
                    workitem = Workitem(sch["context"])
                    workitem.send(self.channel, message=sch["code"],
                                  origin="", target=sch["target"])
                    LOG.debug("Sent '%s' to %s", sch["code"],
                              sch["target"])
                storage.delete("schedule", key)
