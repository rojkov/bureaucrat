from __future__ import absolute_import

import logging
import pika

from ConfigParser import NoSectionError

LOG = logging.getLogger(__name__)

DEFAULT_MESSAGE_QUEUE = 'bureaucrat_msgs'
DEFAULT_STORAGE_DIR = '/tmp/processes'
DEFAULT_TASKQUEUE_TYPE = 'taskqueue'

class ConfigsError(Exception):
    """Configs error."""

class Configs(object):
    """Global configs."""

    _instance = None

    def __init__(self, config):
        """Initialize."""

        try:
            items = dict(config.items("bureaucrat"))
            self._message_queue = items.get("message_queue",
                                            DEFAULT_MESSAGE_QUEUE)
            self._storage_dir = items.get("storage_dir", DEFAULT_STORAGE_DIR)
            self._taskqueue_type = items.get("taskqueue_type",
                                             DEFAULT_TASKQUEUE_TYPE)
        except NoSectionError:
            self._message_queue = DEFAULT_MESSAGE_QUEUE
            self._storage_dir = DEFAULT_STORAGE_DIR
            self._taskqueue_type = DEFAULT_TASKQUEUE_TYPE

        try:
            amqp_items  = dict(config.items("amqp"))
            amqp_host   = amqp_items.get("host", "localhost")
            amqp_user   = amqp_items.get("user", "guest")
            amqp_passwd = amqp_items.get("passwd", "guest")
            amqp_vhost  = amqp_items.get("vhost", "/")
            credentials = pika.PlainCredentials(amqp_user, amqp_passwd)
            self._amqp_params = pika.ConnectionParameters(
                credentials=credentials,
                host=amqp_host,
                virtual_host=amqp_vhost
            )
        except NoSectionError:
            self._amqp_params = pika.ConnectionParameters(host="localhost")

    @classmethod
    def instance(cls, config=None):
        """Instantiate Configs object."""

        if config is None and cls._instance is None:
            raise ConfigsError("Configuration hasn't been loaded")
        elif config is not None and cls._instance is not None:
            raise ConfigsError("Configs instance must be immutable")
        elif config is not None:
            cls._instance = Configs(config)

        return cls._instance

    @property
    def message_queue(self):
        """Return message_queue config parameter."""
        return self._message_queue

    @property
    def storage_dir(self):
        """Return storage_dir config parameter."""
        return self._storage_dir

    @property
    def taskqueue_type(self):
        """Return taskqueue_type config parameter."""
        return self._taskqueue_type

    @property
    def amqp_params(self):
        """Return AMQP parameters."""
        return self._amqp_params
