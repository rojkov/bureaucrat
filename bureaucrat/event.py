import logging

LOG = logging.getLogger(__name__)

class Event(object):

    def __init__(self, channel, event_type):
        """Constructor."""

        self.workitem = None
        self.target = None
        self.channel = channel
        self.type = event_type

    def __str__(self):
        """String representation of event."""

        return "%s [%s]" % (self.target, self.type)
