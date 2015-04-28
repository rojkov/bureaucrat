from __future__ import absolute_import

import json

class Message(object):
    """Message structure."""

    content_type = 'application/x-bureaucrat-message'

    def __init__(self, name, target, origin, payload=None):
        """initialize."""
        self._name = name
        self._target = target
        self._origin = origin
        if payload is None:
            payload = {}
        self._payload = payload

    def __repr__(self):
        """Return pretty print representation."""
        return "<Message:[name=%s, target=%s, origin=%s]>" % \
                (self._name, self._target, self._origin)

    @staticmethod
    def load(bodystr):
        """Load from string."""
        body = json.loads(bodystr)
        msg = Message(body["message"], body["target"], body["origin"],
                      body["payload"])
        return msg

    @property
    def name(self):
        """Return name."""
        return self._name

    @property
    def target(self):
        """Return target."""
        return self._target

    @property
    def target_pid(self):
        """Return target process ID."""
        return self._target.split('_', 1)[0]

    @property
    def origin(self):
        """Return origin."""
        return self._origin

    @property
    def payload(self):
        """Return payload."""
        return self._payload
