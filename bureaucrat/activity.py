import logging
import pika

LOG = logging.getLogger(__name__)

def get_supported_activities():
    """Return list of supported activity types."""
    # TODO: calculate supported activities dynamically and cache
    return ('action', 'sequence')

def create_activity_from_element(process, element, activity_id):
    """Create an activity instance from ElementTree.Element."""

    tag = element.tag
    if tag == 'action':
        return Action.create_from_element(process, element, activity_id)
    elif tag == 'sequence':
        return Sequence.create_from_element(process, element, activity_id)

class Activity(object):
    """Workflow activity."""

    states = ('ready', 'active', 'completed')

    def __init__(self):
        """Constructor."""
        self.state = 'ready'
        self.id = None
        self.process = None

    def __str__(self):
        """String representation."""
        return "%s" % self.id

    @classmethod
    def create_from_element(cls, process, element, activity_id):
        """Create an instance from ElementTree.Element."""
        raise NotImplemented

    def run(self, channel):
        assert self.state == 'ready'
        LOG.debug("Running %s (%s)", self.__class__.__name__, self)
        self.state = 'active'

    def snapshot(self):
        """Return activity snapshot."""
        # TODO: move common code to this base class
        raise NotImplemented

    def reset_state(self, state):
        """Reset activity's state."""
        raise NotImplemented

    def handle_event(self, event, channel):
        """Handle event."""
        raise NotImplemented

class Sequence(Activity):
    """A sequence activity."""

    allowed_child_types = ('action',)

    def __init__(self):
        """Constructor."""
        Activity.__init__(self)
        self.children = []

    @classmethod
    def create_from_element(cls, process, element, activity_id):
        """Create an instance from ElementTree.Element."""
        assert element.tag == 'sequence'
        LOG.debug("Creating sequence")

        sequence = Sequence()
        sequence.id = activity_id
        sequence.process = process
        el_index = 0
        for child in element:
            assert child.tag in cls.allowed_child_types
            activity = create_activity_from_element(process,
                                                    child, "%s_%d" % \
                                                    (activity_id, el_index))
            sequence.children.append(activity)
            el_index = el_index + 1
        return sequence

    def run(self, channel):
        Activity.run(self, channel)
        for activity in self.children:
            if activity.state == 'ready':
                activity.run(channel)
            if activity.state != 'completed':
                break

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

    def handle_event(self, event, channel):
        """Handle event."""

        if not event["activity_id"].startswith(self.id):
            return

        for activity in self.children:

            LOG.debug("%r iterates over %r" % (self, activity))
            if activity.state != 'completed' and \
               event["activity_id"].startswith(activity.id):
                activity.handle_event(event, channel)
                if activity.state != 'completed':
                    LOG.debug("not completed after handling event: %s" % activity)
                    break

            if activity.state == 'ready':
                activity.run(channel)
            if activity.state != 'completed':
                LOG.debug("not completed after running: %s" % activity)
                break
        else:
            LOG.debug("Activity list successfully exhausted")
            self.state = 'completed'


class Action(Activity):
    """An action activity."""

    def __init__(self):
        """Constructor."""
        Activity.__init__(self)
        self.participant = None

    def __str__(self):
        """String representation."""
        return "%s-%s" % (self.participant, self.id)

    @staticmethod
    def create_from_element(process, element, activity_id):
        """Create an instance from ElementTree.Element."""
        assert element.tag == 'action'
        LOG.debug("Creating action")

        action = Action()
        action.id = activity_id
        action.process = process
        action.participant = element.attrib["participant"]
        return action

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

    def run(self, channel):
        """Start action."""
        Activity.run(self, channel)
        wi_body = """{"participant": "%s", "activity_id": "%s", "process_id": "%s"}""" % \
                      (self.participant, self.id, self.process.uuid)
        channel.basic_publish(exchange='',
                              routing_key="taskqueue",
                              body=wi_body,
                              properties=pika.BasicProperties(
                                  delivery_mode=2,
                                  content_type='application/x-bureaucrat-workitem'
                              ))

    def handle_event(self, event, channel):
        """Handle event."""

        LOG.debug("%s handles event." % self)
        if event["activity_id"] == self.id:
            if event["type"] == 'response':
                LOG.debug("Got response for action %s" % self.id)
                self.state = 'completed'

def test():
    LOG.info("Success")

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    test()
