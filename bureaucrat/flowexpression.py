from __future__ import absolute_import

import logging
import pika
import time
import json
from HTMLParser import HTMLParser
import xml.etree.ElementTree as ET

from bureaucrat.context import Context
from bureaucrat.message import Message
from bureaucrat.storage import Storage
from bureaucrat.storage import lock_storage

LOG = logging.getLogger(__name__)

def is_state_final(state):
    """Check if state is final."""
    return state in ('completed', 'aborted', 'canceled')

def _get_supported_activities():
    """Return list of supported types of activities."""
    # TODO: calculate supported activities dynamically and cache
    return ('action', 'sequence', 'switch', 'while', 'all', 'call', 'delay',
            'await')

def _create_fe_from_element(parent_id, element, fei, context):
    """Create a flow expression instance from ElementTree.Element."""

    tag = element.tag
    expr = None
    if tag == 'action':
        expr = Action(parent_id, element, fei, context)
    elif tag == 'sequence':
        expr = Sequence(parent_id, element, fei, context)
    elif tag == 'switch':
        expr = Switch(parent_id, element, fei, context)
    elif tag == 'case':
        expr = Case(parent_id, element, fei, context)
    elif tag == 'while':
        expr = While(parent_id, element, fei, context)
    elif tag == 'all':
        expr = All(parent_id, element, fei, context)
    elif tag == 'call':
        expr = Call(parent_id, element, fei, context)
    elif tag == 'delay':
        expr = Delay(parent_id, element, fei, context)
    elif tag == 'await':
        expr = Await(parent_id, element, fei, context)
    else:
        raise FlowExpressionError("Unknown tag: %s" % tag)
    return expr


@lock_storage
def _subscribe(event, target):
    """Subscribe given target to event."""
    storage = Storage.instance()
    subscriptions = []
    if storage.exists("subscriptions", event):
        subscriptions = json.loads(storage.load("subscriptions", event))
    subscriptions.append({
        "target": target
    })
    storage.save("subscriptions", event, json.dumps(subscriptions))


class FlowExpressionError(Exception):
    """FlowExpression error."""


class FlowExpression(object):
    """Flow expression."""

    allowed_child_types = ()
    is_ctx_allowed = True # TODO: refactor to introduce simple and complex activities
    is_cond_allowed = False

    def __init__(self, parent_id, element, fei, context):
        """Constructor."""

        self.fe_name = self.__class__.__name__.lower()
        assert element.tag == self.fe_name
        LOG.debug("Creating %s", self.fe_name)

        self.state = 'ready'
        self.id = fei
        self.parent_id = parent_id
        self.children = []
        if self.is_ctx_allowed:
            self.context = Context(context)
        else:
            self.context = context

        el_index = 0
        for child in element:
            if child.tag in self.allowed_child_types:
                fexpr = _create_fe_from_element(self.id, child,
                                                "%s_%d" % (fei, el_index),
                                                self.context)
                self.children.append(fexpr)
                el_index = el_index + 1
            else:
                self._parse_non_child(child)

    def __str__(self):
        """String representation."""
        return "%s" % self.id

    def __repr__(self):
        """Instance representation."""
        return "<%s[%s, state='%s']>" % (self.__class__.__name__, self,
                                         self.state)

    def _parse_non_child(self, element):
        """Parse disallowed child element.

        Some flow expressions can contain child elements in their definition
        which are just attributes of them, not other flow expression.
        As an example consider <condition> inside <case>.
        """
        if element.tag == 'context' and self.is_ctx_allowed:
            self.context.parse(element)
        elif element.tag == 'condition' and self.is_cond_allowed:
            html_parser = HTMLParser()
            self.conditions.append(html_parser.unescape(element.text))
        else:
            raise FlowExpressionError("'%s' is disallowed child type" % \
                                      element.tag)

    def snapshot(self):
        """Return flow expression snapshot."""
        snapshot = {
            "id": self.id,
            "state": self.state,
            "type": self.fe_name,
            "children": [child.snapshot() for child in self.children]
        }
        if self.is_ctx_allowed:
            snapshot["context"] = self.context.localprops
        return snapshot

    def reset_state(self, state):
        """Reset activity's state."""
        LOG.debug("Resetting %s's state", self.fe_name)
        assert state["type"] == self.fe_name
        assert state["id"] == self.id
        self.state = state["state"]
        if self.is_ctx_allowed:
            self.context.localprops = state["context"]
        for child, childstate in zip(self.children, state["children"]):
            child.reset_state(childstate)

    def handle_message(self, channel, msg):
        """Handle message.

        This is common code used by all derived classes.
        """

        result = ''

        if self.state == 'completed':
            LOG.debug("%r is done already, %r is ignored", self, msg)
            result = 'ignored'
        elif msg.target is not None and \
                not msg.target.startswith(self.id):
            LOG.debug("%r is not for %r", msg, self)
            result = 'ignored'
        elif self.is_ctx_allowed and self.state == 'active' and \
                msg.name == 'fault' and msg.target == self.id:
            self.state = 'aborting'
            self.context.set('inst:fault', msg.payload)
            all_in_final_state = True
            for child in self.children:
                if not is_state_final(child.state):
                    all_in_final_state = False
                    channel.send(Message(name='terminate', target=child.id,
                                         origin=self.id))
            if all_in_final_state:
                self.state = 'aborted'
                channel.send(Message(name='fault', target=self.parent_id,
                                     origin=self.id, payload=msg.payload))
            result = 'consumed'
        elif self.is_ctx_allowed and self.state == 'active' and \
                msg.name == 'terminate' and msg.target == self.id:
            self.state = 'aborting'
            for child in self.children:
                if not is_state_final(child.state):
                    channel.send(Message(name='terminate', target=child.id,
                                         origin=self.id))
            result = 'consumed'
        elif self.is_ctx_allowed and self.state == 'ready' and \
                msg.name == 'terminate' and msg.target == self.id:
            self.state = 'canceling'
            for child in self.children:
                if not is_state_final(child.state):
                    channel.send(Message(name='terminate', target=child.id,
                                         origin=self.id))
            result = 'consumed'
        elif self.is_ctx_allowed and self.state == 'aborting' and \
                (msg.name == 'canceled' or msg.name == 'aborted' or \
                 msg.name == 'completed') and \
                msg.target == self.id:
            if sum([int(is_state_final(child.state))
                    for child in self.children]) == len(self.children):
                # all children are in a final state
                self.state = 'aborted'
                channel.send(Message(name='fault', target=self.parent_id,
                                     origin=self.id,
                                     payload=self.context.get('inst:fault')))
            result = 'consumed'
        elif self.is_ctx_allowed and self.state == 'canceling' and \
                (msg.name == 'canceled' or msg.name == 'aborted' or \
                 msg.name == 'completed') and msg.target == self.id:
            if sum([int(is_state_final(child.state))
                    for child in self.children]) == len(self.children):
                # all children are in a final state
                channel.send(Message(name='canceled', target=self.parent_id,
                                     origin=self.id))
                self.state = 'canceled'
            result = 'consumed'
        elif not self.is_ctx_allowed and self.state == 'active' and \
                msg.name == 'terminate' and msg.target == self.id:
            self.state = 'aborted'
            channel.send(Message(name='aborted', target=self.parent_id,
                                 origin=self.id))
            result = 'consumed'
        elif not self.is_ctx_allowed and self.state == 'ready' and \
                msg.name == 'terminate' and msg.target == self.id:
            self.state = 'canceled'
            channel.send(Message(name='canceled', target=self.parent_id,
                                 origin=self.id))
            result = 'consumed'
        elif not self.is_ctx_allowed and self.state == 'aborting' and \
                msg.name == 'terminate' and msg.target == self.id:
            self.state = 'aborted'
            channel.send(Message(name='aborted', target=self.parent_id,
                                 origin=self.id))
            result = 'consumed'

        return result

    def _was_activated(self, channel, msg, guard=lambda: True):
        """Check if it's activation message."""

        if self._is_start_message(msg):

            if not guard():
                LOG.debug("Conditions for %r don't hold", self)
                self.state = 'completed'
                channel.send(Message(name='completed', origin=self.id,
                                     target=self.parent_id))
                return 'consumed'

            if len(self.children) > 0:
                self.state = 'active'
                channel.send(Message(name='start', origin=self.id,
                                     target=self.children[0].id))
            else:
                self.state = 'completed'
                channel.send(Message(name='completed', origin=self.id,
                                     target=self.parent_id))
            return 'consumed'
        else:
            return ''

    def _was_sequence_completed(self, channel, msg, guard=lambda: True,
                                compensate=lambda: None):
        """Check if all children in sequence were completed."""

        res = ''
        if self._is_complete_message(msg):
            for index, child in zip(range(0, len(self.children)),
                                    self.children):
                if child.id == msg.origin:
                    if (index + 1) < len(self.children):
                        channel.send(Message(name='start', origin=self.id,
                                             target="%s_%d" % (self.id,
                                                               index + 1)))
                    else:
                        if guard():
                            self.state = 'completed'
                            channel.send(Message(name='completed',
                                                 origin=self.id,
                                                 target=self.parent_id))
                        else:
                            compensate()
                    res = 'consumed'
                    break
        return res

    def _was_consumed_by_child(self, channel, msg):
        """Check if a child consumed the message."""

        res = ''
        for child in self.children:
            if child.handle_message(channel, msg) == 'consumed':
                res = 'consumed'
                break
        return res

    def _is_start_message(self, msg):
        """Return True if the message destined to start the activity."""
        return self.state == 'ready' and msg.name == 'start' \
                and msg.target == self.id

    def _is_complete_message(self, msg):
        """Return True if the message is from completed child."""
        return self.state == 'active' and msg.name == 'completed' \
                and msg.target == self.id

    def reset_children(self):
        """Reset children state to ready."""

        for child in self.children:
            child.state = 'ready'
            child.reset_children()

class Process(FlowExpression):
    """A Process flow expression."""

    allowed_child_types = _get_supported_activities()

    def handle_message(self, channel, msg):
        """Handle message in process instance."""
        LOG.debug("Handling %r in %r", msg, self)

        res = FlowExpression.handle_message(self, channel, msg) or \
                self._was_activated(channel, msg) or \
                self._was_sequence_completed(channel, msg) or \
                self._was_consumed_by_child(channel, msg)
        if res:
            return res

        return 'ignored'

class Sequence(FlowExpression):
    """A sequence activity."""

    allowed_child_types = _get_supported_activities()

    def handle_message(self, channel, msg):
        """Handle message."""

        res = FlowExpression.handle_message(self, channel, msg) or \
                self._was_activated(channel, msg) or \
                self._was_sequence_completed(channel, msg) or \
                self._was_consumed_by_child(channel, msg)
        if res:
            return res

        return 'ignored'

class Action(FlowExpression):
    """An action activity."""

    is_ctx_allowed = False

    def __init__(self, parent_id, element, fei, context):
        """Constructor."""

        FlowExpression.__init__(self, parent_id, element, fei, context)
        self.participant = element.attrib["participant"]

    def __str__(self):
        """String representation."""
        return "%s-%s" % (self.participant, self.id)

    def handle_message(self, channel, msg):
        """Handle message."""

        res = FlowExpression.handle_message(self, channel, msg)
        if res:
            return res

        result = 'ignore'
        if self._is_start_message(msg):
            LOG.debug("Activate participant %s", self.participant)
            self.state = 'active'
            channel.elaborate(self.participant, self.id,
                              self.context.as_dictionary())
            result = 'consumed'
        elif self.state == 'active' and msg.name == 'response':
            LOG.debug("Got response for action %s. Payload: %s",
                      self.id, msg.payload)
            if 'error' in msg.payload:
                LOG.debug("Got error: %s. Aborting...", msg.payload["error"])
                self.state = 'aborting'
                payload = {
                    "code": "ActionError",
                    "error": msg.payload["error"]
                }
                channel.send(Message(name='fault', origin=self.id,
                                     target=self.parent_id, payload=payload))
            else:
                self.context.update(msg.payload)
                self.state = 'completed'
                # reply to parent that the child is done
                channel.send(Message(name='completed', origin=self.id,
                                     target=self.parent_id))
            result = 'consumed'
        else:
            LOG.debug("%r ignores %r", self, msg)

        return result

class Delay(FlowExpression):
    """A delay activity."""

    is_ctx_allowed = False

    def __init__(self, parent_id, element, fei, context):
        """Constructor."""

        FlowExpression.__init__(self, parent_id, element, fei, context)
        self.duration = int(element.attrib["duration"])

    def __str__(self):
        """String representation."""
        return "%s[duration=%s]" % (self.id, self.duration)

    def handle_message(self, channel, msg):
        """Handle msg."""

        res = FlowExpression.handle_message(self, channel, msg)
        if res:
            return res

        result = 'ignore'
        if self._is_start_message(msg):
            LOG.debug("Wait for %s", self.duration)
            self.state = 'active'
            instant = int(time.time()) + self.duration
            channel.schedule_event(target=self.id, code="timeout",
                                   instant=instant)
            result = 'consumed'
        elif self.state == 'active' and msg.name == 'timeout':
            LOG.debug("Time is out for %s", self.id)
            self.state = 'completed'
            # reply to parent that the child is done
            channel.send(Message(name='completed', origin=self.id,
                                 target=self.parent_id))
            result = 'consumed'
        else:
            LOG.debug("%r ignores %r", self, msg)

        return result

class Await(FlowExpression):
    """A await activity."""

    is_ctx_allowed = False
    is_cond_allowed = True

    def __init__(self, parent_id, element, fei, context):
        """Constructor."""

        self.conditions = []
        FlowExpression.__init__(self, parent_id, element, fei, context)
        self.event = element.attrib["event"]

    def __str__(self):
        """String representation."""
        return "%s[event=%s]" % (self.id, self.event)

    def evaluate(self):
        """Check if conditions are met."""

        if len(self.conditions) == 0:
            return True

        for cond in self.conditions:
            if eval(cond, {"context": self.context.as_dictionary()}):
                LOG.debug("Condition %s evaluated to True", cond)
                return True
            else:
                LOG.debug("Condition %s evaluated to False", cond)

        return False

    def handle_message(self, channel, msg):
        """Handle message."""

        res = FlowExpression.handle_message(self, channel, msg)
        if res:
            return res

        result = 'ignore'
        if self._is_start_message(msg):
            LOG.debug("Wait for %s", self.event)
            self.state = 'active'
            _subscribe(event=self.event, target=self.id)
            result = 'consumed'
        elif self.state == 'active' and msg.name == 'triggered':
            LOG.debug("Event '%s' triggered for %s", self.event, self.id)

            if not self.evaluate():
                LOG.debug("Conditions for %r don't hold", self)
                return 'ignored'

            self.state = 'completed'
            # reply to parent that the child is done
            channel.send(Message(name='completed', origin=self.id,
                                 target=self.parent_id))
            result = 'consumed'
        else:
            LOG.debug("%r ignores %r", self, msg)

        return result

class Case(FlowExpression):
    """Case element of switch activity."""

    allowed_child_types = _get_supported_activities()
    is_cond_allowed = True

    def __init__(self, parent_id, element, fei, context):
        """Constructor."""

        self.conditions = []
        FlowExpression.__init__(self, parent_id, element, fei, context)

    def evaluate(self):
        """Check if conditions are met."""

        for cond in self.conditions:
            if eval(cond, {"context": self.context.as_dictionary()}):
                LOG.debug("Condition %s evaluated to True", cond)
                return True
            else:
                LOG.debug("Condition %s evaluated to False", cond)

        return False

    def handle_message(self, channel, msg):
        """Handle message."""
        LOG.debug("handling %r in %r", msg, self)

        res = FlowExpression.handle_message(self, channel, msg) or \
                self._was_activated(channel, msg) or \
                self._was_sequence_completed(channel, msg) or \
                self._was_consumed_by_child(channel, msg)
        if res:
            return res

        return 'ignored'

class Switch(FlowExpression):
    """Switch activity."""

    allowed_child_types = ('case', )

    is_ctx_allowed = False

    def handle_message(self, channel, msg):
        """Handle message."""

        LOG.debug("Handling %r in %r", msg, self)
        res = FlowExpression.handle_message(self, channel, msg)
        if res:
            return res

        if self._is_start_message(msg):
            for case in self.children:
                if case.evaluate():
                    self.state = 'active'
                    channel.send(Message(name='start', origin=self.id,
                                         target=case.id))
                    break
                else:
                    LOG.debug("Condition doesn't hold for %r", case)
            else:
                self.state = 'completed'
            return 'consumed'

        if self._is_complete_message(msg):
            self.state = 'completed'
            channel.send(Message(name='completed', origin=self.id,
                                 target=self.parent_id))
            return 'consumed'

        if self._was_consumed_by_child(channel, msg):
            return 'consumed'

        return 'ignored'

class While(FlowExpression):
    """While activity."""

    allowed_child_types = _get_supported_activities()
    is_cond_allowed = True

    def __init__(self, parent_id, element, fei, context):
        """Constructor."""

        self.conditions = []
        FlowExpression.__init__(self, parent_id, element, fei, context)

    def evaluate(self):
        """Check if conditions are met."""

        for cond in self.conditions:
            if eval(cond, {"context": self.context.as_dictionary()}):
                LOG.debug("Condition %s evaluated to True", cond)
                return True
            else:
                LOG.debug("Condition %s evaluated to False", cond)

        return False

    def handle_message(self, channel, msg):
        """Handle message."""

        def restart():
            self.reset_children()
            channel.send(Message(name='start', target=self.children[0].id,
                                 origin=self.id))

        res = FlowExpression.handle_message(self, channel, msg) or \
                self._was_activated(channel, msg, self.evaluate) or \
                self._was_sequence_completed(channel, msg,
                                             lambda: not self.evaluate(),
                                             restart) or \
                self._was_consumed_by_child(channel, msg)
        if res:
            return res

        return 'ignored'

class All(FlowExpression):
    """All activity."""

    allowed_child_types = _get_supported_activities()

    def handle_message(self, channel, msg):
        """Handle message."""

        res = FlowExpression.handle_message(self, channel, msg)
        if res:
            return res

        if self._is_start_message(msg):
            if len(self.children) > 0:
                self.state = 'active'
                for child in self.children:
                    assert child.state == 'ready'
                    channel.send(Message(name='start', origin=self.id,
                                         target=child.id))
            else:
                self.state = 'completed'
                channel.send(Message(name='completed', origin=self.id,
                                     target=self.parent_id))
            return 'consumed'

        if self._is_complete_message(msg):
            for child in self.children:
                if child.state == 'active':
                    break
            else:
                self.state = 'completed'
                channel.send(Message(name='completed', origin=self.id,
                                     target=self.parent_id))
            return 'consumed'

        if self._was_consumed_by_child(channel, msg):
            return 'consumed'

        return 'ignored'

class Call(FlowExpression):
    """Call activity."""

    is_ctx_allowed = False

    def __init__(self, parent_id, element, fei, context):
        """Constructor."""

        FlowExpression.__init__(self, parent_id, element, fei, context)
        self.process_name = element.attrib["process"]

    def handle_message(self, channel, msg):
        """Handle message."""

        res = FlowExpression.handle_message(self, channel, msg)
        if res:
            return res

        result = 'consumed'
        if self._is_start_message(msg):
            self.state = 'active'
            LOG.debug("Calling a subprocess process")

            assert self.process_name.startswith('$'), \
                    "Only process defs referenced from message are supported."
            ref = self.process_name[1:]
            root = ET.fromstring(self.context.get(ref))
            assert root.tag == 'process'
            root.set('parent', self.id)
            pdef = ET.tostring(root)
            channel._ch.basic_publish(exchange='', # TODO: refactor to avoid private attribute
                                      routing_key='bureaucrat',
                                      body=pdef,
                                      properties=pika.BasicProperties(
                                          delivery_mode=2
                                      ))
        elif self._is_complete_message(msg):
            LOG.debug("Subprocess initiated in %s has completed", self.id)
            self.state = 'completed'
            # reply to parent that the child is done
            channel.send(Message(name='completed', origin=self.id,
                                 target=self.parent_id))
        else:
            LOG.debug("%r ignores %r", self, msg)
            result = 'ignored'

        return result

def test():
    LOG.info("Success")

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    test()
