import logging
import json
import pika

from ConfigParser import NoSectionError
from configs import Configs

LOG = logging.getLogger(__name__)

class WorkitemError(Exception):
    """Workitem error."""


WORKITEM_MIME_TYPE = 'application/x-bureaucrat-workitem'


class Workitem(object):
    """Work item."""

    def __init__(self, fields=None):
        """Work item constructor."""

        if fields is None:
            fields = {}

        self._fields = fields

        self._header = {
            "message": None,
            "origin": None,
            "target": None
        }

    def __repr__(self):
        """Return instance representation string."""
        return "<Workitem[msg=%(message)s, origin=%(origin)s, target=%(target)s]>" % self._header

    @classmethod
    def loads(cls, blob):
        """Load workitem from JSON formatted string."""
        try:
            delivery = json.loads(blob)
            assert delivery["header"]["message"] is not None
            assert delivery["header"]["origin"] is not None
            assert delivery["header"]["target"] is not None
            assert delivery["fields"] is not None
            self = cls(delivery["fields"])
            self._header = delivery["header"]
            return self
        except (ValueError, KeyError, TypeError, AssertionError):
            raise WorkitemError("Can't parse workitem")

    @property
    def origin(self):
        """Return flow expression ID this workitem originates from."""

        return self._header["origin"]

    @property
    def target(self):
        """Return flow expression ID this workitem targets to."""

        return self._header["target"]

    @property
    def target_pid(self):
        """Return target process ID."""
        return self._header["target"].split('_', 1)[0]

    @property
    def fields(self):
        """Return workitem's fields accessible by workers."""

        return self._fields

    @property
    def message(self):
        """Return workitem's message name."""

        return self._header["message"]

    def send(self, channel, message, target, origin):
        """Send a message to the target with the workitem attached."""

        body = {
            "header": {
                "message": message,
                "target": target,
                "origin": origin
            },
            "fields": self._fields
        }
        channel.basic_publish(exchange='',
                              routing_key="bureaucrat_events",
                              body=json.dumps(body),
                              properties=pika.BasicProperties(
                                  delivery_mode=2,
                                  content_type=WORKITEM_MIME_TYPE
                              ))

    def elaborate(self, channel, participant, origin):
        """Elaborate the workitem at a given participant."""

        config = Configs()

        try:
            items = dict(config.items("bureaucrat"))
            queue_type = items.get("taskqueue_type", "taskqueue")
        except NoSectionError:
            LOG.debug("No task queue configs: setting default task queue type")
            queue_type = "taskqueue"

        if queue_type == 'taskqueue':
            body = {
                "header": {
                    "message": 'response',
                    "target": origin,
                    "origin": origin
                },
                "fields": self._fields
            }
            channel.basic_publish(exchange='',
                                  routing_key="worker_%s" % participant,
                                  body=json.dumps(body),
                                  properties=pika.BasicProperties(
                                      delivery_mode=2,
                                      content_type=WORKITEM_MIME_TYPE
                                  ))
        elif queue_type == 'celery':
            body = {
                "header": {
                    "message": 'response',
                    "target": origin,
                    "origin": origin
                },
                "fields": self._fields
            }
            # This is a message in the format acceptable by Celery.
            # The exact format can be found in
            # celery.app.amqp.TaskProducer.publish_task()
            celery_msg = {
                "task": participant,
                "id": self.target_pid,
                "args": (body, ),
                "kwargs": {},
                "retries": 0,
                "eta": None,
                "expires": None,
                "utc": True,
                "callbacks": None,
                "errbacks": None,
                "timelimit": (None, None),
                "taskset": None,
                "chord": None
            }
            channel.basic_publish(exchange='celery',
                                  routing_key="celery",
                                  body=json.dumps(celery_msg),
                                  properties=pika.BasicProperties(
                                      delivery_mode=2,
                                      content_type='application/json',
                                      content_encoding='utf-8'
                                  ))
        else:
            raise WorkitemError("Unknown task queue type: %s" % queue_type)
