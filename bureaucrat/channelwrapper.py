from __future__ import absolute_import

import logging
import pika
import json
import uuid

from bureaucrat.configs import Configs

LOG = logging.getLogger(__name__)

class ChannelWrapperError(Exception):
    """ChannelWrapper error."""

class ChannelWrapper(object):
    """Wrapper around AMQP channel used to send messages."""

    def __init__(self, channel):
        """Initialize wrapper."""

        self._ch = channel

    def send(self, message):
        """Send a message to the target with the workitem attached."""

        body = {
            "message": message.name,
            "target": message.target,
            "origin": message.origin,
            "payload": message.payload
        }
        self._ch.basic_publish(exchange='',
                               routing_key=Configs.instance().message_queue,
                               body=json.dumps(body),
                               properties=pika.BasicProperties(
                                   delivery_mode=2,
                                   content_type=message.content_type,
                                   content_encoding='utf-8'
                               ))

    def elaborate(self, participant, origin, payload):
        """Elaborate the workitem at a given participant."""

        config = Configs.instance()

        if config.taskqueue_type == 'taskqueue':
            body = {
                "header": {
                    "message": 'response',
                    "target": origin,
                    "origin": origin
                },
                "fields": payload
            }
            self._ch.basic_publish(exchange='',
                                   routing_key="worker_%s" % participant,
                                   body=json.dumps(body),
                                   properties=pika.BasicProperties(
                                       delivery_mode=2,
                                       content_type='application/x-bureaucrat-workitem'
                                   ))
        elif config.taskqueue_type == 'celery':
            body = {
                "message": 'response',
                "target": origin,
                "origin": origin,
                "payload": payload
            }
            # This is a message in the format acceptable by Celery.
            # The exact format can be found in
            # celery.app.amqp.TaskProducer.publish_task()
            celery_msg = {
                "task": participant,
                "id": "%s" % uuid.uuid4(),
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
            self._ch.basic_publish(exchange='celery',
                                   routing_key="celery",
                                   body=json.dumps(celery_msg),
                                   properties=pika.BasicProperties(
                                       delivery_mode=2,
                                       content_type='application/json',
                                       content_encoding='utf-8'
                                   ))
        else:
            raise ChannelWrapperError("Unknown task queue type: %s" % \
                                      config.taskqueue_type)

    def schedule_event(self, instant, code, target):
        """Schedule event for the context."""
        body = {
            "instant": instant,
            "code": code,
            "target": target
        }
        self._ch.basic_publish(exchange='',
                               routing_key="bureaucrat_schedule",
                               body=json.dumps(body),
                               properties=pika.BasicProperties(
                                   delivery_mode=2,
                                   content_type='application/json',
                                   content_encoding='utf-8'
                               ))

