import logging
import pika
import sexpdata
from HTMLParser import HTMLParser

from event import Event
from workitem import Workitem

LOG = logging.getLogger(__name__)

def is_activity(tag):
    return tag in ('sequence', 'action', 'switch')

def get_supported_activities():
    """Return list of supported activity types."""
    # TODO: calculate supported activities dynamically and cache
    return ('action', 'sequence')

def create_activity_from_element(parent, element, activity_id):
    """Create an activity instance from ElementTree.Element."""

    tag = element.tag
    if tag == 'action':
        return Action(parent, element, activity_id)
    elif tag == 'sequence':
        return Sequence(parent, element, activity_id)
    elif tag == 'switch':
        return Switch(parent, element, activity_id)
    else:
        LOG.error("Unknown tag: %s" % tag)

class Activity(object):
    """Workflow activity."""

    states = ('ready', 'active', 'completed')

    def __init__(self, parent, element, activity_id):
        """Constructor."""
        self.state = 'ready'
        self.id = activity_id
        self.parent = parent

    def __str__(self):
        """String representation."""
        return "%s" % self.id

    def __repr__(self):
        """Instance representation."""
        return "<%s[%s]>" % (self.__class__.__name__, self)

    def snapshot(self):
        """Return activity snapshot."""
        # TODO: move common code to this base class
        raise NotImplemented

    def reset_state(self, state):
        """Reset activity's state."""
        raise NotImplemented

    def handle_event(self, event):
        """Handle event."""
        raise NotImplemented

class Sequence(Activity):
    """A sequence activity."""

    allowed_child_types = ('action', 'switch')

    # TODO: move to superclass?
    def __init__(self, parent, element, activity_id):
        """Constructor."""

        assert element.tag == 'sequence'
        LOG.debug("Creating sequence")
        Activity.__init__(self, parent, element, activity_id)

        self.children = []

        el_index = 0
        for child in element:
            assert child.tag in self.allowed_child_types
            activity = create_activity_from_element(self, child, "%s_%d" % \
                                                    (activity_id, el_index))
            self.children.append(activity)
            el_index = el_index + 1

    def snapshot(self):
        """Return activity snapshot."""
        return {
            "id": self.id,
            "state": self.state,
            "type": "sequence",
            "children": [activity.snapshot() for activity in self.children]
        }

    def reset_state(self, state):
        """Reset sequence's state."""
        LOG.debug("Resetting sequence's state")
        assert state["type"] == 'sequence'
        assert state["id"] == self.id
        self.state = state["state"]
        for child, childstate in zip(self.children, state["children"]):
            child.reset_state(childstate)

    def handle_event(self, event):
        """Handle event."""

        if self.state == 'completed':
            LOG.debug("%r is done already, %r is ignored" % (self, event))
            return 'ignored'

        if event.target is not None and not event.target.startswith(self.id):
            LOG.debug("%r is not for %r" % (event, self))
            return 'ignored'

        if self.state == 'active' and event.name == 'completed' \
                                  and event.target == self.id:
            for index, child in zip(range(0, len(self.children)), self.children):
                if child.id == event.workitem.fei:
                    if (index + 1) < len(self.children):
                        event.target = "%s_%d" % (self.id, index + 1)
                        event.workitem.event_name = 'start'
                        event.workitem.fei = self.id
                        event.trigger()
                    else:
                        self.state = 'completed'
                        event.target = self.parent.id
                        event.workitem.event_name = 'completed'
                        event.workitem.fei = self.id
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


class Action(Activity):
    """An action activity."""

    def __init__(self, parent, element, activity_id):
        """Constructor."""

        assert element.tag == 'action'
        LOG.debug("Creating action")
        Activity.__init__(self, parent, element, activity_id)
        self.participant = element.attrib["participant"]

    def __str__(self):
        """String representation."""
        return "%s-%s" % (self.participant, self.id)

    def snapshot(self):
        """Return activity snapshot."""
        return {
            "id": self.id,
            "state": self.state,
            "type": "action"
        }

    def reset_state(self, state):
        """Reset action's state."""
        LOG.debug("Resetting action's state")
        assert state["type"] == 'action'
        assert state["id"] == self.id
        self.state = state["state"]

    def handle_event(self, event):
        """Handle event."""

        if self.state == 'completed':
            LOG.debug("%r is done already, %r is ignored" % (self, event))
            return 'ignored'

        if event.target is not None and event.target != self.id:
            LOG.debug("%r is not for %r" % (event, self))
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
            event.target = self.parent.id
            event.workitem.event_name = "completed"
            event.workitem.fei = self.id
            event.trigger()
            result = 'consumed'
        else:
            LOG.debug("%r ignores %r" %(self, event))

        return result

class Case(object):
    """Case element of switch activity."""

    def __init__(self, parent, element, fei):
        """Constructor."""

        self.id = fei
        self.state = 'ready'
        self.conditions = []
        self.activities = []
        self.parent = parent

        el_index = 0
        for child in element:
            if child.tag == 'condition':
                html_parser = HTMLParser()
                self.conditions.append(html_parser.unescape(child.text))
            elif is_activity(child.tag):
                self.activities.append(
                    create_activity_from_element(self, child,
                                                 "%s_%s" % (fei, el_index)))
                el_index = el_index + 1
            else:
                LOG.error("Unknown element: %s", child.tag)

    # TODO: drop it
    def __repr__(self):
        """Instance representation."""
        return "<%s[%s]>" % (self.__class__.__name__, self.id)

    def evaluate(self):
        """Check if conditions are met."""

        for cond in self.conditions:
            if (eval(cond)):
                LOG.debug("Condition %s evaluated to True" % cond)
                return True
            else:
                LOG.debug("Condition %s evaluated to False" % cond)

        return False

    def snapshot(self):
        """Return case snapshot."""
        return {
            "id": self.id,
            "state": self.state,
            "type": "case",
            "children": [activity.snapshot() for activity in self.activities]
        }

    def reset_state(self, state):
        """Reset case's state."""
        LOG.debug("Resetting case's state")
        assert state["type"] == 'case'
        assert state["id"] == self.id
        self.state = state["state"]
        for child, childstate in zip(self.activities, state["children"]):
            child.reset_state(childstate)

    def handle_event(self, event):
        """Handle event."""
        LOG.debug("handling %r in %r" % (event, self))

        if self.state == 'completed':
            LOG.debug("%r is done already, %r is ignored" % (self, event))
            return 'ignored'

        if event.target is not None and not event.target.startswith(self.id):
            LOG.debug("%r is not for %r" % (event, self))
            return 'ignored'

        if self.state == 'active' and event.name == 'completed' \
                                  and event.target == self.id:
            for index, child in zip(range(0, len(self.activities)), self.activities):
                if child.id == event.workitem.fei:
                    if (index + 1) < len(self.activities):
                        event.target = "%s_%d" % (self.id, index + 1)
                        event.workitem.event_name = 'start'
                        event.workitem.fei = self.id
                    else:
                        self.state = 'completed'
                        event.target = self.parent.id
                        event.workitem.event_name = 'completed'
                        event.workitem.fei = self.id
                    LOG.debug("Trigger %r to continue from %r. Activities total: %d" % (event, self, len(self.activities)))
                    event.trigger()
                    return 'consumed'
            else:
                LOG.warning("No origin found")

        if self.state == 'ready' and event.name == 'start' \
                                 and event.target == self.id:

            if not self.evaluate():
                LOG.debug("Conditions for %r don't hold", self)
                return 'ignored'

            if len(self.activities) > 0:
                self.state = 'active'
                event.target = self.activities[0].id
                LOG.debug("Start handling event in children")
                event.trigger()
            else:
                self.state = 'completed'
            return 'consumed'

        for child in self.activities:
            if child.handle_event(event) == 'consumed':
                return 'consumed'

        LOG.debug("%r was ignored in %r" % (event, self))
        return 'ignored'

class Switch(Activity):
    """Switch activity."""

    def __init__(self, parent, element, activity_id):
        """Constructor."""

        assert element.tag == 'switch'
        LOG.debug("Creating switch")
        Activity.__init__(self, parent, element, activity_id)
        self.cases = []

        el_index = 0
        for child in element:
            assert child.tag in 'case'
            case = Case(self, child, "%s_%d" % (activity_id, el_index))
            self.cases.append(case)
            el_index = el_index + 1

    def snapshot(self):
        """Return switch snapshot."""
        return {
            "id": self.id,
            "state": self.state,
            "type": "switch",
            "cases": [case.snapshot() for case in self.cases]
        }

    def reset_state(self, state):
        """Reset switch's state."""
        LOG.debug("Resetting switch's state")
        assert state["type"] == 'switch'
        assert state["id"] == self.id
        self.state = state["state"]
        for child, childstate in zip(self.cases, state["cases"]):
            child.reset_state(childstate)

    def handle_event(self, event):
        """Handle event."""

        if self.state == 'completed':
            LOG.debug("%r is done already, %r is ignored" % (self, event))
            return 'ignored'

        if event.target is not None and not event.target.startswith(self.id):
            LOG.debug("%r is not for %r" % (event, self))
            return 'ignored'

        if self.state == 'active' and event.name == 'completed' \
                                  and event.target == self.id:
            self.state = 'completed'
            event.target = self.parent.id
            event.workitem.event_name = 'completed'
            event.workitem.fei = self.id
            event.trigger()
            return 'consumed'

        if self.state == 'ready' and event.name == 'start' \
                                 and event.target == self.id:
            for case in self.cases:
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

        for child in self.cases:
            if child.handle_event(event) == 'consumed':
                return 'consumed'

        return 'ignored'

def test():
    LOG.info("Success")

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    test()
