import sys
import pika
import logging
import traceback

from daemonlib import Daemon
from process import Process
from workitem import Workitem
from event import Event

LOG = logging.getLogger(__name__)

def log_trace(func):
    """Log traceback before raising exception."""
    def new_func(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except:
            exc_type, exc_value, tb = sys.exc_info()
            for line in traceback.format_tb(tb):
                LOG.error(line.strip())
            LOG.error("%s: %s" % (exc_type, exc_value))
            raise
    return new_func

class Bureaucrat(Daemon):
    """Bureaucrat daemon."""

    pidfile = "/var/run/bureaucrat.pid"

    def __init__(self, config):
        """Initialize application."""

        self.channel = None
        self.connection = None
        super(Bureaucrat, self).__init__(config)

    @log_trace
    def launch_process(self, channel, method, header, body):
        """Handle delivery."""

        LOG.debug("Method: %r" % method)
        LOG.debug("Header: %r" % header)
        LOG.debug("Body: %r" % body)
        process = Process.create(body)
        workitem = Workitem.create(process.uuid, 'start')
        event = Event(channel, workitem)
        if process.handle_event(event):
            LOG.debug("%r is completed" % process)
        process.suspend()
        channel.basic_ack(method.delivery_tag)

    @log_trace
    def handle_event(self, channel, method, header, body):
        """Handle event."""

        LOG.debug("Method: %r" % method)
        LOG.debug("Header: %r" % header)
        LOG.debug("Handling event with Body: %r" % body)
        try:
            workitem = Workitem()
            workitem.loads(body)
        except WorkitemError as err:
            # Report error and accept message
            LOG.error("%s" % err)
            channel.basic_ack(method.delivery_tag)
            return

        event = Event(channel, workitem)
        process = Process.load("/tmp/processes/definition-%s" % \
                               workitem.pid)
        process.resume(workitem.pid)
        if process.handle_event(event):
            LOG.debug("%r is completed" % process)
        process.suspend()
        channel.basic_ack(method.delivery_tag)

    def run(self):
        """Event cycle."""

        LOG.debug("create connection")
        self.connection = pika.BlockingConnection(self.amqp_params)
        LOG.debug("Bureaucrat connected")
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue="bureaucrat", durable=True,
                                   exclusive=False, auto_delete=False)
        self.channel.queue_declare(queue="bureaucrat_events", durable=True,
                                   exclusive=False, auto_delete=False)
        self.channel.basic_consume(self.launch_process, queue="bureaucrat")
        self.channel.basic_consume(self.handle_event, queue="bureaucrat_events")
        self.channel.start_consuming()

    def cleanup(self, signum, frame):
        """Handler for termination signals."""

        LOG.debug("cleanup")
        self.channel.stop_consuming()
        self.connection.close()
        sys.exit(0)

if __name__ == '__main__':
    Bureaucrat.main()
