import logging
import pika
import json
import sexpdata
from HTMLParser import HTMLParser
import xml.etree.ElementTree as ET

from workitem import Workitem

LOG = logging.getLogger(__name__)

def get_supported_flowexpressions():
    """Return list of supported types of flow expressions."""
    # TODO: calculate supported activities dynamically and cache
    return ('action', 'sequence', 'switch', 'while', 'all', 'call')

class FlowExpressionError(Exception):
    """FlowExpression error."""

def create_fe_from_element(parent_id, element, fei):
    """Create a flow expression instance from ElementTree.Element."""

    tag = element.tag
    expr = None
    if tag == 'action':
        expr = Action(parent_id, element, fei)
    elif tag == 'sequence':
        expr = Sequence(parent_id, element, fei)
    elif tag == 'switch':
        expr = Switch(parent_id, element, fei)
    elif tag == 'case':
        expr = Case(parent_id, element, fei)
    elif tag == 'while':
        expr = While(parent_id, element, fei)
    elif tag == 'all':
        expr = All(parent_id, element, fei)
    elif tag == 'call':
        expr = Call(parent_id, element, fei)
    else:
        raise FlowExpressionError("Unknown tag: %s" % tag)
    return expr

class FlowExpression(object):
    """Flow expression."""

    states = ('ready', 'active', 'completed')
    allowed_child_types = ()

    def __init__(self, parent_id, element, fei):
        """Constructor."""

        self.fe_name = self.__class__.__name__.lower()
        assert element.tag == self.fe_name
        LOG.debug("Creating %s", self.fe_name)

        self.state = 'ready'
        self.id = fei
        self.parent_id = parent_id
        self.context = None
        self.children = []

        if len(self.allowed_child_types) == 0:
            return

        el_index = 0
        for child in element:
            if child.tag in self.allowed_child_types:
                fexpr = create_fe_from_element(self.id, child,
                                               "%s_%d" % (fei, el_index))
                self.children.append(fexpr)
                el_index = el_index + 1
            else:
                self.parse_non_child(child)

    def __str__(self):
        """String representation."""
        return "%s" % self.id

    def __repr__(self):
        """Instance representation."""
        return "<%s[%s, state='%s']>" % (self.__class__.__name__, self,
                                         self.state)

    def parse_non_child(self, element):
        """Parse disallowed child element.

        Some flow expressions can contain child elements in their definition
        which are just attributes of them, not other flow expression.
        As an example consider <condition> inside <case>.
        """
        raise FlowExpressionError("'%s' is disallowed child type" % element.tag)

    def snapshot(self):
        """Return flow expression snapshot."""
        return {
            "id": self.id,
            "state": self.state,
            "type": self.fe_name,
            "context": self.context,
            "children": [child.snapshot() for child in self.children]
        }

    def reset_state(self, state):
        """Reset activity's state."""
        LOG.debug("Resetting %s's state", self.fe_name)
        assert state["type"] == self.fe_name
        assert state["id"] == self.id
        self.state = state["state"]
        self.context = state["context"]
        for child, childstate in zip(self.children, state["children"]):
            child.reset_state(childstate)

    def handle_workitem(self, channel, workitem):
        """Handle workitem."""
        raise NotImplementedError()

    def _can_be_ignored(self, workitem):
        """Check if workitem can be safely ignored."""

        can_be_ignored = False

        if self.state == 'completed':
            LOG.debug("%r is done already, %r is ignored", self, workitem)
            can_be_ignored = True
        elif workitem.target is not None and \
                not workitem.target.startswith(self.id):
            LOG.debug("%r is not for %r", workitem, self)
            can_be_ignored = True

        return can_be_ignored

    def reset_children(self):
        """Reset children state to ready."""

        for child in self.children:
            child.state = 'ready'
            child.reset_children()

class ProcessError(FlowExpressionError):
    """Process error."""

class Process(FlowExpression):
    """A Process flow expression."""

    allowed_child_types = get_supported_flowexpressions()

    def parse_non_child(self, element):
        """Parse process's fields."""

        if element.tag == 'fields':
            self.context = json.loads(element.text)
        else:
            raise ProcessError("Unknown element: %s" % element.tag)

    def handle_workitem(self, channel, workitem):
        """Handle workitem in process instance."""
        LOG.debug("Handling %r in %r", workitem, self)

        if workitem.message == 'start' and workitem.target == self.id:
            if len(self.children) > 0:
                self.state = 'active'
                workitem = Workitem(self.context)
                workitem.send(channel, message='start', origin=self.id,
                              target=self.children[0].id)
            else:
                self.state = 'completed'
                workitem.send(channel, message='completed', origin=self.id,
                              target=self.parent_id)
            return 'consumed'

        if self.state == 'active' and workitem.message == 'completed' \
                                  and workitem.target == self.id:
            for index, child in zip(range(0, len(self.children)), self.children):
                if child.id == workitem.origin:
                    if (index + 1) < len(self.children):
                        workitem.send(channel, message='start', origin=self.id,
                                      target="%s_%d" % (self.id, (index + 1)))
                    else:
                        self.state = 'completed'
                        workitem.send(channel, message='completed',
                                      origin=self.id, target=self.parent_id)
                    return 'consumed'

        for child in self.children:
            if child.handle_workitem(channel, workitem) == 'consumed':
                return 'consumed'

        return 'ignored'

class Sequence(FlowExpression):
    """A sequence activity."""

    allowed_child_types = get_supported_flowexpressions()

    def handle_workitem(self, channel, workitem):
        """Handle workitem."""

        if self._can_be_ignored(workitem):
            return 'ignored'

        if self.state == 'active' and workitem.message == 'completed' \
                                  and workitem.target == self.id:
            for index, child in zip(range(0, len(self.children)), self.children):
                if child.id == workitem.origin:
                    if (index + 1) < len(self.children):
                        workitem.send(channel, message='start', origin=self.id,
                                      target="%s_%d" % (self.id, index + 1))
                    else:
                        self.state = 'completed'
                        workitem.send(channel, message='completed',
                                      origin=self.id, target=self.parent_id)
                    return 'consumed'

        if self.state == 'ready' and workitem.message == 'start' \
                                 and workitem.target == self.id:
            if len(self.children) > 0:
                self.state = 'active'
                workitem.send(channel, message='start', origin=self.id,
                              target=self.children[0].id)
            else:
                self.state = 'completed'
                workitem.send(channel, message='completed',
                              origin=self.id, target=self.parent_id)
            return 'consumed'

        for child in self.children:
            if child.handle_workitem(channel, workitem) == 'consumed':
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

    def handle_workitem(self, channel, workitem):
        """Handle workitem."""

        if self._can_be_ignored(workitem):
            return 'ignored'

        result = 'ignore'
        if self.state == 'ready' and workitem.message == 'start':
            LOG.debug("Activate participant %s", self.participant)
            self.state = 'active'
            workitem.elaborate(channel, self.participant, self.id)
            result = 'consumed'
        elif self.state == 'active' and workitem.message == 'response':
            LOG.debug("Got response for action %s", self.id)
            self.state = 'completed'
            # reply to parent that the child is done
            workitem.send(channel, message='completed', origin=self.id,
                          target=self.parent_id)
            result = 'consumed'
        else:
            LOG.debug("%r ignores %r", self, workitem)

        return result

class CaseError(FlowExpressionError):
    """Case error."""

class Case(FlowExpression):
    """Case element of switch activity."""

    allowed_child_types = get_supported_flowexpressions()

    def __init__(self, parent_id, element, fei):
        """Constructor."""

        self.conditions = []
        FlowExpression.__init__(self, parent_id, element, fei)

    def parse_non_child(self, element):
        """Parse case's conditions."""

        if element.tag == 'condition':
            html_parser = HTMLParser()
            self.conditions.append(html_parser.unescape(element.text))
        else:
            raise CaseError("Unknown element: %s" % element.tag)

    def evaluate(self, workitem):
        """Check if conditions are met."""

        for cond in self.conditions:
            if eval(cond, {"workitem": workitem}):
                LOG.debug("Condition %s evaluated to True", cond)
                return True
            else:
                LOG.debug("Condition %s evaluated to False", cond)

        return False

    def handle_workitem(self, channel, workitem):
        """Handle workitem."""
        LOG.debug("handling %r in %r", workitem, self)

        if self._can_be_ignored(workitem):
            return 'ignored'

        if self.state == 'active' and workitem.message == 'completed' \
                                  and workitem.target == self.id:
            for index, child in zip(range(0, len(self.children)),
                                    self.children):
                if child.id == workitem.origin:
                    if (index + 1) < len(self.children):
                        workitem.send(channel, message='start', origin=self.id,
                                      target="%s_%d" % (self.id, index + 1))
                    else:
                        self.state = 'completed'
                        workitem.send(channel, message='completed',
                                      target=self.parent_id, origin=self.id)
                    LOG.debug("Send %r to continue from %r. " + \
                              "Activities total: %d",
                              workitem, self, len(self.children))
                    return 'consumed'
            LOG.warning("No origin found")

        if self.state == 'ready' and workitem.message == 'start' \
                                 and workitem.target == self.id:

            if not self.evaluate(workitem):
                LOG.debug("Conditions for %r don't hold", self)
                return 'ignored'

            if len(self.children) > 0:
                self.state = 'active'
                LOG.debug("Start handling workitem in children")
                workitem.send(channel, message='start', origin=self.id,
                              target=self.children[0].id)
            else:
                self.state = 'completed'
                workitem.send(channel, message='completed', origin=self.id,
                              target=self.parent_id)

            return 'consumed'

        for child in self.children:
            if child.handle_workitem(channel, workitem) == 'consumed':
                return 'consumed'

        LOG.debug("%r was ignored in %r", workitem, self)
        return 'ignored'

class Switch(FlowExpression):
    """Switch activity."""

    allowed_child_types = ('case', )

    def handle_workitem(self, channel, workitem):
        """Handle workitem."""

        LOG.debug("Handling %r in %r", workitem, self)
        if self._can_be_ignored(workitem):
            return 'ignored'

        if self.state == 'active' and workitem.message == 'completed' \
                                  and workitem.target == self.id:
            self.state = 'completed'
            workitem.send(channel, message='completed', origin=self.id,
                          target=self.parent_id)
            return 'consumed'

        if self.state == 'ready' and workitem.message == 'start' \
                                 and workitem.target == self.id:
            for case in self.children:
                if case.evaluate(workitem):
                    self.state = 'active'
                    workitem.send(channel, message='start', origin=self.id,
                                  target=case.id)
                    break
                else:
                    LOG.debug("Condition doesn't hold for %r", case)
            else:
                self.state = 'completed'
            return 'consumed'

        for child in self.children:
            if child.handle_workitem(channel, workitem) == 'consumed':
                return 'consumed'

        return 'ignored'

class WhileError(FlowExpressionError):
    """While error."""

class While(FlowExpression):
    """While activity."""

    allowed_child_types = get_supported_flowexpressions()

    def __init__(self, parent_id, element, fei):
        """Constructor."""

        self.conditions = []
        FlowExpression.__init__(self, parent_id, element, fei)

    def parse_non_child(self, element):
        """Parse case's conditions."""

        if element.tag == 'condition':
            html_parser = HTMLParser()
            self.conditions.append(html_parser.unescape(element.text))
        else:
            raise WhileError("Unknown element: %s" % element.tag)

    def evaluate(self, workitem):
        """Check if conditions are met."""

        for cond in self.conditions:
            if eval(cond, {"workitem": workitem}):
                LOG.debug("Condition %s evaluated to True", cond)
                return True
            else:
                LOG.debug("Condition %s evaluated to False", cond)

        return False

    def handle_workitem(self, channel, workitem):
        """Handle workitem."""

        if self._can_be_ignored(workitem):
            return 'ignored'

        if self.state == 'ready' and workitem.message == 'start' \
                                 and workitem.target == self.id:

            if not self.evaluate(workitem):
                LOG.debug("Conditions for %r don't hold", self)
                self.state = 'completed'
                workitem.send(channel, message='completed', origin=self.id,
                              target=self.parent_id)
                return 'consumed'

            if len(self.children) > 0:
                self.state = 'active'
                LOG.debug("Start handling workitem in children")
                workitem.send(channel, message='start', origin=self.id,
                              target=self.children[0].id)
            else:
                raise WhileError("While activity can't be empty")

            return 'consumed'

        if self.state == 'active' and workitem.message == 'completed' \
                                  and workitem.target == self.id:
            for index, child in zip(range(0, len(self.children)),
                                    self.children):
                if child.id == workitem.origin:
                    if (index + 1) < len(self.children):
                        workitem.send(channel, message='start', origin=self.id,
                                      target="%s_%d" % (self.id, index + 1))
                    else:
                        if not self.evaluate(workitem):
                            self.state = 'completed'
                            workitem.send(channel, message='completed',
                                          origin=self.id, target=self.parent_id)
                        else:
                            self.reset_children()
                            workitem.send(channel, message='start',
                                          origin=self.id,
                                          target=self.children[0].id)
                    LOG.debug("Trigger %r to continue from %r. " + \
                              "Activities total: %d",
                              workitem, self, len(self.children))
                    return 'consumed'
            LOG.warning("No origin found")

        for child in self.children:
            if child.handle_workitem(channel, workitem) == 'consumed':
                return 'consumed'

class All(FlowExpression):
    """All activity."""

    allowed_child_types = get_supported_flowexpressions()

    def handle_workitem(self, channel, workitem):
        """Handle workitem."""

        if self._can_be_ignored(workitem):
            return 'ignored'

        if self.state == 'ready' and workitem.message == 'start' \
                                 and workitem.target == self.id:
            if len(self.children) > 0:
                self.state = 'active'
                self.context = workitem.fields
                for child in self.children:
                    assert child.state == 'ready'
                    workitem.send(channel, message='start', origin=self.id,
                                  target=child.id)
            else:
                self.state = 'completed'
                workitem.send(channel, message='completed', origin=self.id,
                              target=self.parent_id)
            return 'consumed'

        if self.state == 'active' and workitem.message == 'completed' \
                                  and workitem.target == self.id:
            self.context.update(workitem.fields)
            for child in self.children:
                if child.state == 'active':
                    break
            else:
                self.state = 'completed'
                witem = Workitem(self.context)
                witem.send(channel, message='completed', origin=self.id,
                           target=self.parent_id)
            return 'consumed'

        for child in self.children:
            if child.handle_workitem(channel, workitem) == 'consumed':
                return 'consumed'

class Call(FlowExpression):
    """Call activity."""

    def __init__(self, parent_id, element, fei):
        """Constructor."""

        FlowExpression.__init__(self, parent_id, element, fei)
        self.process_name = element.attrib["process"]

    def handle_workitem(self, channel, workitem):
        """Handle workitem."""

        if self._can_be_ignored(workitem):
            return 'ignored'

        result = 'consumed'
        if self.state == 'ready' and workitem.message == 'start':
            self.state = 'active'
            LOG.debug("Calling a subprocess process")

            assert self.process_name.startswith('$'), \
                    "Only process defs referenced from workitem are supported."
            ref = self.process_name[1:]
            root = ET.fromstring(workitem.fields[ref])
            assert root.tag == 'process'
            root.set('parent', self.id)
            pdef = ET.tostring(root)
            channel.basic_publish(exchange='',
                                  routing_key='bureaucrat',
                                  body=pdef,
                                  properties=pika.BasicProperties(
                                      delivery_mode=2
                                  ))
        elif self.state == 'active' and workitem.message == 'completed' \
                                    and workitem.target == self.id:
            LOG.debug("Subprocess initiated in %s has completed", self.id)
            self.state = 'completed'
            # reply to parent that the child is done
            workitem.send(channel, message='completed', origin=self.id,
                          target=self.parent_id)
        else:
            LOG.debug("%r ignores %r", self, workitem)
            result = 'ignored'

        return result

def test():
    LOG.info("Success")

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    test()
