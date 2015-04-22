from __future__ import absolute_import

import sys
import pika
import logging
import logging.config
import traceback
import daemon
import uuid
import signal
import fcntl
import json
import os
import os.path

from optparse import OptionParser
from ConfigParser import ConfigParser

from bureaucrat.workflow import Workflow
from bureaucrat.workitem import Workitem, WorkitemError
from bureaucrat.schedule import Schedule
from bureaucrat.configs import Configs
from bureaucrat.storage import Storage
from bureaucrat.storage import lock_storage

LOG = logging.getLogger(__name__)

PID_FILE = "/var/run/bureaucrat.pid"

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


def parse_cmdline(defaults):
    """Parse commandline options."""

    parser = OptionParser()
    parser.add_option("-f", "--foreground", dest="foreground",
                      action="store_true", default=False,
                      help="don't daemonize")
    parser.add_option("-c", "--config", dest="config",
                      default="/etc/taskqueue/config.ini",
                      help="path to config file")
    parser.add_option("-p", "--pid-file", dest="pidfile",
                      default=defaults["pidfile"])

    (options, _) = parser.parse_args()
    return options


class PidFile(object):
    """Context manager that locks a pid file.

    Implemented as class not generator because daemon.py is
    calling .__exit__() with no parameters instead of the None, None, None
    specified by PEP-343.
    copy&pasted from
    http://code.activestate.com/recipes/577911-context-manager-for-a-daemon-pid-file/
    """
    # pylint: disable=R0903

    def __init__(self, path):
        self.path = path
        self.pidfile = None

    def __enter__(self):
        self.pidfile = open(self.path, "a+")
        try:
            fcntl.flock(self.pidfile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            raise SystemExit("Already running according to " + self.path)
        self.pidfile.seek(0)
        self.pidfile.truncate()
        self.pidfile.write(str(os.getpid()))
        self.pidfile.flush()
        self.pidfile.seek(0)
        return self.pidfile

    def __exit__(self, exc_type=None, exc_value=None, exc_tb=None):
        try:
            self.pidfile.close()
        except IOError as err:
            # ok if file was just closed elsewhere
            if err.errno != 9:
                raise
        os.remove(self.path)


class Bureaucrat(object):
    """Bureaucrat daemon."""

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

    @log_trace
    @lock_storage
    def handle_event(self, channel, method, header, body):
        """Handle workitem."""

        LOG.debug("Method: %r", method)
        LOG.debug("Header: %r", header)
        LOG.debug("Handling workitem with Body: %r", body)
        msg = json.loads(body)
        eventname = msg["event"]
        storage = Storage.instance()
        if storage.exists("subscriptions", eventname):
            subscriptions = json.loads(storage.load("subscriptions",
                                                    eventname))
            for subscr in subscriptions:
                subscr["context"]["event"] = msg
                workitem = Workitem(subscr["context"])
                workitem.send(channel, message='triggered',
                              origin='', target=subscr["target"])
            storage.delete("subscriptions", eventname)
        channel.basic_ack(method.delivery_tag)

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
        self.channel.queue_declare(queue=config.event_queue, durable=True,
                                   exclusive=False, auto_delete=False)
        self.channel.queue_declare(queue="bureaucrat_schedule", durable=True,
                                   exclusive=False, auto_delete=False)
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(self.launch_process, queue="bureaucrat")
        self.channel.basic_consume(self.handle_workitem,
                                   queue=config.message_queue)
        self.channel.basic_consume(self.handle_event,
                                   queue=config.event_queue)
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

    @classmethod
    def main(cls):
        """Bureaucrat entry point."""

        options = parse_cmdline({"pidfile": PID_FILE})

        # configure logging
        logging.config.fileConfig(options.config,
                                  disable_existing_loggers=False)

        config = ConfigParser()
        config.read(options.config)
        Configs.instance(config)

        daemon_obj = cls()

        context = daemon.DaemonContext()

        context.pidfile = PidFile(options.pidfile)
        if options.foreground:
            context.detach_process = False
            context.stdout = sys.stdout
            context.stderr = sys.stdout

        context.signal_map = {
            signal.SIGTERM: daemon_obj.cleanup,
            signal.SIGHUP: daemon_obj.cleanup
        }

        with context:
            daemon_obj.run()
