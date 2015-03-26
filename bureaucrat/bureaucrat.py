import sys
import pika
import logging

from daemonlib import Daemon
from process import Process
from workitem import Workitem

LOG = logging.getLogger(__name__)

class Bureaucrat(Daemon):
    """Bureaucrat daemon."""

    pidfile = "/var/run/bureaucrat.pid"

    def __init__(self, config):
        """Initialize application."""

        self.channel = None
        self.connection = None
        super(Bureaucrat, self).__init__(config)

    def handle_delivery(self, channel, method, header, body):
        """Handle delivery."""

        LOG.debug("Method: %r" % method)
        LOG.debug("Header: %r" % header)
        LOG.debug("Body: %r" % body)
        process = Process.create(body)
        process.execute(channel)
        channel.basic_ack(method.delivery_tag)

    def handle_event(self, channel, method, header, body):
        """Handle event."""

        LOG.debug("Method: %r" % method)
        LOG.debug("Header: %r" % header)
        LOG.debug("Handling event with Body: %r" % body)
        try:
            workitem = Workitem('application/x-bureaucrat-workitem')
            workitem.loads(body)
        except WorkitemError as err:
            # Report error and accept message
            LOG.error("%s" % err)
            channel.basic_ack(method.delivery_tag)
            return

        event = workitem._body # TODO: disgusting!
        process = Process.load("/tmp/processes/definition-%s" % \
                               event["process_id"])
        process.resume(event["process_id"])
        process.handle_event(event, channel)
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
        self.channel.basic_consume(self.handle_delivery, queue="bureaucrat")
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
