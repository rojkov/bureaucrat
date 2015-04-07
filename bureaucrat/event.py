import logging
import pika

LOG = logging.getLogger(__name__)

class Event(object):
    """Wrapper around Workitem providing communication channel."""

    def __init__(self, channel, workitem):
        """Constructor."""

        self.workitem = workitem
        self.channel = channel

    def __str__(self):
        """String representation of event."""

        return "%s,%s" % (self.name, self.target)

    def __repr__(self):
        """Stringified instance."""
        return "<%s[%s]>" % (self.__class__.__name__, self)

    @property
    def target(self):
        """Return event target."""
        return self.workitem.target

    @target.setter
    def target(self, new_target):
        """Update event target."""
        self.workitem.target = new_target

    @property
    def name(self):
        """Return event name."""
        return self.workitem.event_name

    def trigger(self):
        """Publish the event for consumption by process."""

        self.channel.basic_publish(exchange='',
                                   routing_key="bureaucrat_events",
                                   body=self.workitem.dumps(),
                                   properties=pika.BasicProperties(
                                       delivery_mode=2,
                                       content_type=self.workitem.mime_type
                                   ))

    def elaborate_at(self, worker_type):
        """Send workitem to remote worker to elaborate."""

        self.workitem.worker_type = worker_type
        self.workitem.event_name = 'response'
        self.channel.basic_publish(exchange='',
                                   routing_key="taskqueue",
                                   body=self.workitem.dumps(),
                                   properties=pika.BasicProperties(
                                       delivery_mode=2,
                                       content_type=self.workitem.mime_type
                                   ))
