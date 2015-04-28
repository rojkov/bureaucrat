import unittest
import xml.etree.ElementTree as ET

from mock import Mock
from mock import patch

from bureaucrat.flowexpression import Call
from bureaucrat.context import Context
from bureaucrat.message import Message

processdsc = """<?xml version="1.0"?>
<call process="$some_process_name" />
"""

subprocessdsc = """<?xml version="1.0"?>
<process>
    <action participant="test1" />
</process>
"""

class TestCall(unittest.TestCase):
    """Tests for Call activity."""

    def setUp(self):
        """Set up SUT."""
        xml_element = ET.fromstring(processdsc)
        self.fexpr = Call('fake-id', xml_element, 'fake-id_0', Context())
        self.ch = Mock()
        self.ch.send = Mock()

    # TODO: move these two cases to a base class
    def test_handle_message_completed_state(self):
        """Test Call.handle_message() when While is completed."""

        self.fexpr.state = 'completed'
        msg = Message(name='start', target='fake-id_0', origin='fake-id')
        result = self.fexpr.handle_message(self.ch, msg)
        self.assertEqual(result, 'ignored')

    def test_handle_message_wrong_target(self):
        """Test Call.handle_message() when message targeted not to it."""

        msg = Message(name='start', target='fake-id_10', origin='fake-id')
        self.fexpr.state = 'active'
        result = self.fexpr.handle_message(self.ch, msg)
        self.assertEqual(result, 'ignored')

    def test_handle_message_start(self):
        """Test Call.handle_message() with 'start' message."""

        msg = Message(name='start', target='fake-id_0', origin='fake-id')
        self.fexpr.context.set('some_process_name', subprocessdsc)
        self.fexpr.state = 'ready'
        result = self.fexpr.handle_message(self.ch, msg)
        self.assertEqual(result, 'consumed')
        self.assertEqual(self.fexpr.state, 'active')
        self.ch._ch.basic_publish.assert_called_once()

    def test_handle_message_completed(self):
        """Test Call.handle_message() with 'completed' message."""

        msg = Message(name='completed', target='fake-id_0',
                      origin='other-fake-id')
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
