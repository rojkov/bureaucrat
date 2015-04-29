import unittest

import xml.etree.ElementTree as ET

from mock import Mock
from mock import patch
from mock import call

from bureaucrat.flowexpression import FlowExpression
from bureaucrat.flowexpression import _get_supported_activities
from bureaucrat.flowexpression import FlowExpressionError
from bureaucrat.context import Context
from bureaucrat.message import Message

class ComplexExpression(FlowExpression):
    allowed_child_types = ('complexexpression', 'simpleexpression')
    is_ctx_allowed = True

class SimpleExpression(FlowExpression):
    allowed_child_types = ()
    is_ctx_allowed = False

def tag2class_map(parent_id, element, fei, context):
    tag = element.tag
    expr = None
    if tag == 'simpleexpression':
        expr = SimpleExpression(parent_id, element, fei, context)
    elif tag == 'complexexpression':
        expr = ComplexExpression(parent_id, element, fei, context)
    assert expr is not None
    return expr

def fake_et_iterator(parent):
    """Fake iterator over child elements."""

    def internal_fake_iterator(parent):
        while False:
            yield None

    xml_element1 = Mock()
    xml_element1.tag = 'simpleexpression'
    xml_element1.__iter__ = internal_fake_iterator
    elements = [xml_element1]

    for elem in elements:
        yield elem

class TestConstrcutorFlowExpression(unittest.TestCase):
    """Tests for FlowExpression's constrcutor."""

    def setUp(self):
        """Set up test case."""
        self.xml_element = Mock()
        self.xml_element.tag = 'flowexpression'

    def test_constructor_no_children(self):
        """Test FlowExpression.__init__() for simple expression."""

        def fake_iterator(parent):
            while False:
                yield None
        self.xml_element.__iter__ = fake_iterator
        fexpr = FlowExpression('fake-id', self.xml_element, 'fake-id_0',
                               Context())
        self.assertTrue(fexpr.id == 'fake-id_0')

    def test_constructor(self):
        """Test FlowExpression.__init__() for complex expression."""

        self.xml_element.__iter__ = fake_et_iterator
        self.xml_element.tag = 'complexexpression'

        with patch('bureaucrat.flowexpression._create_fe_from_element') as t2cmap:
            t2cmap = tag2class_map
            fexpr = ComplexExpression('fake-id', self.xml_element, 'fake-id_0',
                                   Context())
            self.assertTrue(fexpr.id == 'fake-id_0')
            self.assertTrue(len(fexpr.children) == 1)


procdsc = """
    <complexexpression>
        <simpleexpression />
        <simpleexpression />
        <complexexpression>
            <simpleexpression />
            <simpleexpression />
        </complexexpression>
        <simpleexpression />
    </complexexpression>
"""

class TestFlowExpression(unittest.TestCase):
    """Tests for FlowExpression."""

    def setUp(self):
        """Set up test case."""

        self.ch = Mock()
        with patch('bureaucrat.flowexpression._create_fe_from_element') as t2cmap:
            t2cmap = tag2class_map
            self.root = ComplexExpression('', ET.fromstring(procdsc),
                                          'fake-id', Context())

    def test_handle_message_fault_received(self):
        """Test FlowExpression.handle_message() with fault message.

        The 'fault' message is received from the first child which is
        in the 'active' state. The root activity is supposed to
        send 'terminate' message to all its children.

        Also the activity is supposed to raise the 'inst:fault' singal
        in its context.
        """

        msg = Message(name='fault', target='fake-id', origin='fake-id_0',
                      payload={'code': 'GenericError'})
        self.root.state = 'active'
        self.root.children[0].state = 'aborted'
        with patch('bureaucrat.flowexpression.Message') as MockMsg:
            msg0 = Message(name='terminate', target='fake-id_0',
                           origin='fake-id')
            msg1 = Message(name='terminate', target='fake-id_1',
                           origin='fake-id')
            msg2 = Message(name='terminate', target='fake-id_2',
                           origin='fake-id')
            msg3 = Message(name='terminate', target='fake-id_3',
                           origin='fake-id')
            MockMsg.side_effect = [msg0, msg1, msg2, msg3]
            result = self.root.handle_message(self.ch, msg)
            self.assertEqual(self.root.state, 'aborting')
            self.assertEqual(result, 'consumed')

            expected = [
                call(name='terminate', target='fake-id_0', origin='fake-id'),
                call(name='terminate', target='fake-id_1', origin='fake-id'),
                call(name='terminate', target='fake-id_2', origin='fake-id'),
                call(name='terminate', target='fake-id_3', origin='fake-id')
            ]
            self.assertEqual(MockMsg.call_args_list, expected)

            expected = [call(msg0), call(msg1), call(msg2), call(msg3)]
            self.assertEqual(self.ch.send.call_args_list, expected)

            self.assertEqual(self.root.context.get('inst:fault'),
                             'GenericError')

    def test_handle_message_canceled_received(self):
        """Test FlowExpression.handle_message() with single canceled message.

        When a complex activity in the 'aborting' state recieves 'canceled'
        or 'aborted' message and there are still children in non final state
        the activity is supposed to do nothing.
        """

        msg_canceled = Message(name='canceled', target='fake-id',
                             origin='fake-id_1')
        msg_aborted = Message(name='aborted', target='fake-id',
                              origin='fake-id_0')
        self.root.state = 'aborting'
        self.root.children[0].state = 'aborted'
        self.root.children[1].state = 'canceled'
        self.root.children[2].state = 'aborting'
        self.root.children[3].state = 'ready'
        result = self.root.handle_message(self.ch, msg_aborted)
        self.assertEqual(result, 'consumed')
        self.assertEqual(self.root.state, 'aborting')
        result = self.root.handle_message(self.ch, msg_canceled)
        self.assertEqual(result, 'consumed')
        self.assertEqual(self.root.state, 'aborting')
        self.assertEqual(self.ch.send.call_args_list, [])

    def test_handle_message_canceled_all_final(self):
        """Test FlowExpression.handle_message() with last canceled message.

        When a complex activity in the 'aborting' state recieves a 'canceled'
        or 'aborted' message, all its children are in a final state and
        there are no fault handlers registered for the fault signal the
        activity is supposed to change its state to 'aborted' and to send
        a 'fault' message to its parent.
        """

        msg_canceled = Message(name='canceled', target='fake-id',
                             origin='fake-id_3')
        self.root.state = 'aborting'
        self.root.children[0].state = 'aborted'
        self.root.children[1].state = 'canceled'
        self.root.children[2].state = 'aborted'
        self.root.children[3].state = 'canceled'
        with patch('bureaucrat.flowexpression.Message') as MockMsg:
            newmsg = Message(name='fault', target='', origin='fake-id')
            MockMsg.return_value = newmsg
            result = self.root.handle_message(self.ch, msg_canceled)
            self.assertEqual(result, 'consumed')
            MockMsg.assert_called_once_with(name='fault', target='',
                                            origin='fake-id')
            self.ch.send.assert_called_once_with(newmsg)
            self.assertEqual(self.root.state, 'aborted')
