import logging

LOG = logging.getLogger(__name__)

class Event(object):

    def __init__(self, workitem, channel):
        """Constructor."""

        self.workitem = workitem
        self.channel = channel

    def __str__(self):
        """String representation of event."""

        return "%s-%s" % (self.workitem.process_id, self.workitem.activity_id)
