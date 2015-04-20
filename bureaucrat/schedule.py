from __future__ import absolute_import

import logging
import time
import json
import fcntl
import os
import os.path

from ConfigParser import NoSectionError

from bureaucrat.workflow import setup_storage # TODO: refactor storage code
from bureaucrat.workflow import DEFAULT_PROCESS_DIR
from bureaucrat.workitem import Workitem
from bureaucrat.configs import Configs

LOG = logging.getLogger(__name__)

LOCK_FILE = '/tmp/bureaucrat-schedule.lock'

class Schedule(object):
    """Implements scheduled events."""

    def __init__(self, channel):
        """Initialize instance."""

        self.channel = channel
        config = Configs()
        try:
            items = dict(config.items("bureaucrat"))
            storage_dir = items.get("process_dir", DEFAULT_PROCESS_DIR)
        except NoSectionError:
            storage_dir = DEFAULT_PROCESS_DIR
        setup_storage(storage_dir)
        self.schedule_dir = os.path.join(storage_dir, "schedule")

    def register(self, code, instant, target, context):
        """Register new schedule."""
        LOG.debug("Register '%s' for %s at %d", code, target, instant)

        assert type(instant) is int

        with open(LOCK_FILE, 'w') as fd:
            # TODO: implement the lock as context
            fcntl.lockf(fd, fcntl.LOCK_EX)
            file_path = os.path.join(self.schedule_dir, "%d" % instant)
            schedules = []
            if os.path.exists(file_path):
                with open(file_path, 'r') as sc_fhdl:
                    schedules = json.load(sc_fhdl)
            schedules.append({
                "code": code,
                "target": target,
                "context": context
            })
            with open(file_path, 'w') as sc_fhdl:
                json.dump(schedules, sc_fhdl)
            fcntl.lockf(fd, fcntl.LOCK_UN)

    def handle_alarm(self):
        """Load schedule."""

        LOG.debug("Handling alarm")
        with open(LOCK_FILE, 'w') as fd:
            timestamp = int(time.time())
            for fname in os.listdir(self.schedule_dir):
                if timestamp >= int(fname):
                    fpath = os.path.join(self.schedule_dir, fname)
                    schedules = []
                    with open(fpath, 'r') as fhdl:
                        schedules = json.load(fhdl)
                    for sch in schedules:
                        workitem = Workitem(sch["context"])
                        workitem.send(self.channel, message=sch["code"],
                                      origin="", target=sch["target"])
                        LOG.debug("Sent '%s' to %s", sch["code"],
                                  sch["target"])
                    os.unlink(fpath)
            fcntl.lockf(fd, fcntl.LOCK_UN)
