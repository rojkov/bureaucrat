import logging
import pika
import sexpdata
from HTMLParser import HTMLParser

from event import Event
from workitem import Workitem

LOG = logging.getLogger(__name__)

def is_activity(tag):
    return tag in ('sequence', 'action', 'switch')

def get_supported_flowexpressions():
    """Return list of supported types of flow expressions."""
    # TODO: calculate supported activities dynamically and cache
    return ('action', 'sequence', 'switch')

def create_fe_from_element(parent_id, element, fei):
    """Create a flow expression instance from ElementTree.Element."""

    tag = element.tag
    if tag == 'action':
        return Action(parent_id, element, fei)
    elif tag == 'sequence':
        return Sequence(parent_id, element, fei)
    elif tag == 'switch':
        return Switch(parent_id, element, fei)
    elif tag == 'case':
        return Case(parent_id, element, fei)
    else:
        LOG.error("Unknown tag: %s" % tag)

class FlowExpression(object):
    """Flow expression."""

    states = ('ready', 'active', 'completed')
    allowed_child_types = ()

    def __init__(self, parent_id, element, fei):
        """Constructor."""

        self.fe_name = self.__class__.__name__.lower()
        assert element.tag == self.fe_name
        LOG.debug("Creating %s" % self.fe_name)

        self.state = 'ready'
        self.id = fei
        self.parent_id = parent_id
        self.children = []

        if len(self.allowed_child_types) == 0:
            return

        el_index = 0
        for child in element:
            assert child.tag in self.allowed_child_types
            fe = create_fe_from_element(self.id, child, "%s_%d" % (fei, el_index))
            self.children.append(fe)
            el_index = el_index + 1

    def __str__(self):
        """String representation."""
        return "%s" % self.id

    def __repr__(self):
        """Instance representation."""
        return "<%s[%s]>" % (self.__class__.__name__, self)

    def snapshot(self):
        """Return flow expression snapshot."""
        return {
            "id": self.id,
            "state": self.state,
            "type": self.fe_name,
            "children": [child.snapshot() for child in self.children]
        }

    def reset_state(self, state):
        """Reset activity's state."""
        LOG.debug("Resetting %s's state" % self.fe_name)
        assert state["type"] == self.fe_name
        assert state["id"] == self.id
        self.state = state["state"]
        for child, childstate in zip(self.children, state["children"]):
            child.reset_state(childstate)

    def handle_event(self, event):
        """Handle event."""
        raise NotImplemented

    def _can_be_ignored(self, event):
        """Check if event can be safely ignored."""

        can_be_ignored = False

        if self.state == 'completed':
            LOG.debug("%r is done already, %r is ignored" % (self, event))
            can_be_ignored = True
        elif event.target is not None and not event.target.startswith(self.id):
            LOG.debug("%r is not for %r" % (event, self))
            can_be_ignored = True

        return can_be_ignored

class Sequence(FlowExpression):
    """A sequence activity."""

    allowed_child_types = ('action', 'switch', 'sequence')

    def handle_event(self, event):
        """Handle event."""

        if self._can_be_ignored(event):
            return 'ignored'

        if self.state == 'active' and event.name == 'completed' \
                                  and event.target == self.id:
            for index, child in zip(range(0, len(self.children)), self.children):
                if child.id == event.workitem.origin:
                    if (index + 1) < len(self.children):
                        event.target = "%s_%d" % (self.id, index + 1)
                        event.workitem.event_name = 'start'
                    else:
                        self.state = 'completed'
                        event.target = self.parent_id
                        event.workitem.event_name = 'completed'
                    event.workitem.origin = self.id
                    event.trigger()
                    return 'consumed'

        if self.state == 'ready' and event.name == 'start' \
                                 and event.target == self.id:
            if len(self.children) > 0:
                self.state = 'active'
                event.target = self.children[0].id
                event.trigger()
            else:
                self.state = 'completed'
            return 'consumed'

        for child in self.children:
            if child.handle_event(event) == 'consumed':
                return 'consumed'

        return 'ignored'

class Action(FlowExpression):
    """An action activity."""

    def __init__(self, parent_id, element, fei):
        """Constructor."""

        FlowExpression.__init__(self, parent_id, element, fei)
        self.participant = element.attrib["participant"]

    def __str__(self):
        """String representation."""
        return "%s-%s" % (self.participant, self.id)

    def handle_event(self, event):
        """Handle event."""

        if self._can_be_ignored(event):
            return 'ignored'

        result = 'ignore'
        if self.state == 'ready' and event.name == 'start':
            LOG.debug("Activate participant %s" % self.participant)
            self.state = 'active'
            event.elaborate_at(self.participant)
            result = 'consumed'
        elif self.state == 'active' and event.name == 'response':
            LOG.debug("Got response for action %s" % self.id)
            self.state = 'completed'
            # reply to parent that the child is done
            event.target = self.parent_id
            event.workitem.event_name = "completed"
            event.workitem.origin = self.id
            event.trigger()
            result = 'consumed'
        else:
            LOG.debug("%r ignores %r" %(self, event))

        return result

class Case(FlowExpression):
    """Case element of switch activity."""

    allowed_child_types = ('action', 'sequence', 'switch')

    def __init__(self, parent_id, element, fei):
        """Constructor."""

        self.fe_name = self.__class__.__name__.lower()
        self.id = fei
        self.state = 'ready'
        self.conditions = []
        self.children = []
        self.parent_id = parent_id

        el_index = 0
        for child in element:
            if child.tag == 'condition':
                html_parser = HTMLParser()
                self.conditions.append(html_parser.unescape(child.text))
            elif is_activity(child.tag):
                self.children.append(
                    create_fe_from_element(self.id, child,
                                           "%s_%s" % (fei, el_index)))
                el_index = el_index + 1
            else:
                LOG.error("Unknown element: %s", child.tag)

    def evaluate(self):
        """Check if conditions are met."""

        for cond in self.conditions:
            if (eval(cond)):
                LOG.debug("Condition %s evaluated to True" % cond)
                return True
            else:
                LOG.debug("Condition %s evaluated to False" % cond)

        return False

    def handle_event(self, event):
        """Handle event."""
        LOG.debug("handling %r in %r" % (event, self))

        if self._can_be_ignored(event):
            return 'ignored'

        if self.state == 'active' and event.name == 'completed' \
                                  and event.target == self.id:
            for index, child in zip(range(0, len(self.children)), self.children):
                if child.id == event.workitem.origin:
                    if (index + 1) < len(self.children):
                        event.target = "%s_%d" % (self.id, index + 1)
                        event.workitem.event_name = 'start'
                        event.workitem.origin = self.id
                    else:
                        self.state = 'completed'
                        event.target = self.parent_id
                        event.workitem.event_name = 'completed'
                        event.workitem.origin = self.id
                    LOG.debug("Trigger %r to continue from %r. Activities total: %d" % (event, self, len(self.children)))
                    event.trigger()
                    return 'consumed'
            else:
                LOG.warning("No origin found")

        if self.state == 'ready' and event.name == 'start' \
                                 and event.target == self.id:

            if not self.evaluate():
                LOG.debug("Conditions for %r don't hold", self)
                return 'ignored'

            if len(self.children) > 0:
                self.state = 'active'
                event.target = self.children[0].id
                LOG.debug("Start handling event in children")
                event.trigger()
            else:
                self.state = 'completed'
            return 'consumed'

        for child in self.children:
            if child.handle_event(event) == 'consumed':
                return 'consumed'

        LOG.debug("%r was ignored in %r" % (event, self))
        return 'ignored'

class Switch(FlowExpression):
    """Switch activity."""

    allowed_child_types = ('case', )

    def handle_event(self, event):
        """Handle event."""

        if self._can_be_ignored(event):
            return 'ignored'

        if self.state == 'active' and event.name == 'completed' \
                                  and event.target == self.id:
            self.state = 'completed'
            event.target = self.parent_id
            event.workitem.event_name = 'completed'
            event.workitem.origin = self.id
            event.trigger()
            return 'consumed'

        if self.state == 'ready' and event.name == 'start' \
                                 and event.target == self.id:
            for case in self.children:
                if case.evaluate():
                    self.state = 'active'
                    event.target = case.id
                    event.trigger()
                    break
                else:
                    LOG.debug("Condition doesn't hold for %r" % case)
            else:
                self.state = 'completed'
            return 'consumed'

        for child in self.children:
            if child.handle_event(event) == 'consumed':
                return 'consumed'

        return 'ignored'

def test():
    LOG.info("Success")

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    test()
