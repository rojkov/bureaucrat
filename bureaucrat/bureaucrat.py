import sys
import pika
import logging
import traceback
import uuid

from daemonlib import Daemon
from workflow import Workflow
from workitem import Workitem, WorkitemError

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
            LOG.error("%s: %s", exc_type, exc_value)
            raise
    return new_func


class Bureaucrat(Daemon):
    """Bureaucrat daemon."""

    pidfile = "/var/run/bureaucrat.pid"

    def __init__(self):
        """Initialize application."""

        self.channel = None
        self.connection = None
        super(Bureaucrat, self).__init__()

    @log_trace
    def launch_process(self, channel, method, header, body):
        """Handle delivery."""

        LOG.debug("Method: %r", method)
        LOG.debug("Header: %r", header)
        LOG.debug("Body: %r", body)
        wflow = Workflow.create_from_string(body, "%s" % uuid.uuid4())
        workitem = Workitem()
        workitem.send(channel, message='start', target=wflow.process.id,
                      origin='')
        channel.basic_ack(method.delivery_tag)

    @log_trace
    def handle_workitem(self, channel, method, header, body):
        """Handle workitem."""

        LOG.debug("Method: %r", method)
        LOG.debug("Header: %r", header)
        LOG.debug("Handling workitem with Body: %r", body)
        try:
            workitem = Workitem.loads(body)
        except WorkitemError as err:
            # Report error and accept message
            LOG.error("%s", err)
            channel.basic_ack(method.delivery_tag)
            return

        if workitem.target == '':
            LOG.debug("The process %s has finished", workitem.origin)
        else:
            wflow = Workflow.load(workitem.target_pid)
            wflow.process.handle_workitem(channel, workitem)
            wflow.save()
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
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(self.launch_process, queue="bureaucrat")
        self.channel.basic_consume(self.handle_workitem,
                                   queue="bureaucrat_events")
        self.channel.start_consuming()

    def cleanup(self, signum, frame):
        """Handler for termination signals."""

        LOG.debug("cleanup")
        self.channel.stop_consuming()
        self.connection.close()
        sys.exit(0)

if __name__ == '__main__':
    Bureaucrat.main()
