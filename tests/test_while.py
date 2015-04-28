import unittest
import xml.etree.ElementTree as ET
from mock import Mock
from mock import patch

from bureaucrat.flowexpression import While
from bureaucrat.context import Context
from bureaucrat.message import Message

processdsc_true = """<?xml version="1.0"?>
<while>
    <condition>True</condition>
    <action participant="test1" />
    <action participant="test2" />
</while>
"""

processdsc_false = """<?xml version="1.0"?>
<while>
    <condition>False</condition>
    <action participant="test1" />
    <action participant="test2" />
</while>
"""

class TestWhile(unittest.TestCase):
    """Tests for While activity."""

    processdsc = processdsc_true

    def setUp(self):
        xml_element = ET.fromstring(self.processdsc)
        self.fexpr = While('fake-id', xml_element, 'fake-id_0', Context())
        self.ch = Mock()

    def test_handle_message_completed_state(self):
        """Test While.handle_message() when While is completed."""

        msg = Message(name='start', target='fake-id_0', origin='fake-id')
        self.fexpr.state = 'completed'
        result = self.fexpr.handle_message(self.ch, msg)
        self.assertEqual(result, 'ignored')

    def test_handle_message_wrong_target(self):
        """Test While.handle_message() when message targeted not to it."""

        msg = Message(name='start', target='fake-id_10', origin='fake-id')
        self.fexpr.state = 'active'
        result = self.fexpr.handle_message(self.ch, msg)
        self.assertEqual(result, 'ignored')

    def test_handle_message_response(self):
        """Test While.handle_message() with message workitem."""

        msg = Message(name='response', target='fake-id_0_0',
                      origin='fake-id_0_0')
        self.fexpr.state = 'active'
        self.fexpr.children[0].state = 'active'
        result = self.fexpr.handle_message(self.ch, msg)
        self.assertEqual(result, 'consumed')

    def test_handle_message_completed_not_last(self):
        """Test While.handle_message() with completed msg from first child."""

        msg = Message(name='completed', target='fake-id_0',
                      origin='fake-id_0_0')
        newmsg = Message(name='start', target='fake-id_0_1',
                         origin='fake-id_0')
        self.fexpr.state = 'active'
        with patch('bureaucrat.flowexpression.Message') as MockMessage:
            MockMessage.return_value = newmsg
            result = self.fexpr.handle_message(self.ch, msg)
            self.assertEqual(result, 'consumed')
            MockMessage.assert_called_once_with(name='start',
                                                target='fake-id_0_1',
                                                origin='fake-id_0')
            self.ch.send.assert_called_once_with(newmsg)

class TestWhileTrueCondition(TestWhile):
    """Tests for While with conditions evaluated to True."""

    processdsc = processdsc_true

    def test_handle_message_start(self):
        """Test While.handle_message() with start event."""

        msg = Message(name='start', target='fake-id_0', origin='fake-id')
        self.fexpr.state = 'ready'
        newmsg = Message(name='start', target='fake-id_0_0',
                         origin='fake-id_0')
        with patch('bureaucrat.flowexpression.Message') as MockMessage:
            MockMessage.return_value = newmsg
            result = self.fexpr.handle_message(self.ch, msg)
            MockMessage.assert_called_once_with(name='start',
                                                target='fake-id_0_0',
                                                origin='fake-id_0')
            self.assertEqual(result, 'consumed')
            self.assertEqual(self.fexpr.state, 'active')
            self.ch.send.assert_called_once_with(newmsg)

    def test_handle_message_completed_last(self):
        """Test While.handle_message() with completed event from last child."""

        msg = Message(name='completed', target='fake-id_0',
                      origin='fake-id_0_1')
        newmsg = Message(name='start', target='fake-id_0_0', origin='fake-id_0')
        self.fexpr.state = 'active'
        with patch('bureaucrat.flowexpression.Message') as MockMessage:
            MockMessage.return_value = newmsg
            result = self.fexpr.handle_message(self.ch, msg)
            self.assertEqual(result, 'consumed')
            self.assertEqual(self.fexpr.state, 'active')
            MockMessage.assert_called_once_with(name='start',
                                                target='fake-id_0_0',
                                                origin='fake-id_0')
            self.ch.send.assert_called_once_with(newmsg)

class TestWhileFalseCondition(TestWhile):
    """Tests for While with conditions evaluated to False."""

    processdsc = processdsc_false

    def test_handle_message_start(self):
        """Test While.handle_message() with start message."""

        msg = Message(name='start', target='fake-id_0', origin='fake-id')
        newmsg = Message(name='completed', target='fake-id',
                         origin='fake-id_0')
        self.fexpr.state = 'ready'
        with patch('bureaucrat.flowexpression.Message') as MockMessage:
            MockMessage.return_value = newmsg
            result = self.fexpr.handle_message(self.ch, msg)
            self.assertEqual(result, 'consumed')
            self.assertEqual(self.fexpr.state, 'completed')
            MockMessage.assert_called_once_with(name='completed',
                                                target='fake-id',
                                                origin='fake-id_0')
            self.ch.send.assert_called_once_with(newmsg)

    def test_handle_message_completed_last(self):
        """Test While.handle_message() with completed msg from last child."""

        msg = Message(name='completed', target='fake-id_0',
                      origin='fake-id_0_1')
        self.fexpr.state = 'active'
        newmsg = Message(name='completed', target='fake-id',
                         origin='fake-id_0')
        with patch('bureaucrat.flowexpression.Message') as MockMessage:
            MockMessage.return_value = newmsg
            result = self.fexpr.handle_message(self.ch, msg)
            self.assertEqual(result, 'consumed')
            self.assertEqual(self.fexpr.state, 'completed')
            MockMessage.assert_called_once_with(name='completed',
                                                target='fake-id',
                                                origin='fake-id_0')
            self.ch.send.assert_called_once_with(newmsg)
