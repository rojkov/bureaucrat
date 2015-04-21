from __future__ import absolute_import

import sys
import pika
import logging
import traceback
import uuid
import signal
import json

from bureaucrat.daemonlib import Daemon
from bureaucrat.workflow import Workflow
from bureaucrat.workitem import Workitem, WorkitemError
from bureaucrat.schedule import Schedule
from bureaucrat.configs import Configs

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
        self.schedule = None
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

    @log_trace
    def add_schedule(self, channel, method, header, body):
        """Add new scheduled event."""
        LOG.debug("Method: %r", method)
        LOG.debug("Header: %r", header)
        LOG.debug("Handling workitem with Body: %r", body)
        sch = json.loads(body)
        self.schedule.register(instant=sch["instant"], code=sch["code"],
                               target=sch["target"], context=sch["context"])
        channel.basic_ack(method.delivery_tag)

    def handle_alarm(self, signum, frame):
        """Handle timer signal."""
        LOG.debug("Handling timer signal")
        self.schedule.handle_alarm()

    def run(self):
        """Event cycle."""

        config = Configs.instance()
        LOG.debug("create connection")
        self.connection = pika.BlockingConnection(config.amqp_params)
        LOG.debug("Bureaucrat connected")
        self.channel = self.connection.channel()
        self.schedule = Schedule(self.channel)
        self.channel.queue_declare(queue="bureaucrat", durable=True,
                                   exclusive=False, auto_delete=False)
        self.channel.queue_declare(queue=config.message_queue, durable=True,
                                   exclusive=False, auto_delete=False)
        self.channel.queue_declare(queue="bureaucrat_schedule", durable=True,
                                   exclusive=False, auto_delete=False)
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(self.launch_process, queue="bureaucrat")
        self.channel.basic_consume(self.handle_workitem,
                                   queue=config.message_queue)
        self.channel.basic_consume(self.add_schedule,
                                   queue="bureaucrat_schedule")
        signal.signal(signal.SIGALRM, self.handle_alarm)
        signal.setitimer(signal.ITIMER_REAL, 60, 60)
        self.channel.start_consuming()

    def cleanup(self, signum, frame):
        """Handler for termination signals."""

        LOG.debug("cleanup")
        self.channel.stop_consuming()
        self.connection.close()
        sys.exit(0)
