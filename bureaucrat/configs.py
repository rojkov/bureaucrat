from __future__ import absolute_import

import logging

LOG = logging.getLogger(__name__)

class ConfigsError(Exception):
    """Configs error."""

class Configs(object):
    """Global configs."""

    _config = None

    def __new__(cls, config=None):
        """Instantiate Configs object."""

        if config is None and cls._config is None:
            raise ConfigsError("Configuration hasn't been loaded")
        elif config is not None and cls._config is not None:
            raise ConfigsError("Configs instance must be immutable")
        elif config is not None:
            cls._config = config

        return cls._config
