import unittest

import xml.etree.ElementTree as ET
from mock import Mock
from mock import patch

from bureaucrat.flowexpression import Switch
from bureaucrat.context import Context
from bureaucrat.message import Message

processdsc = """<?xml version="1.0"?>
<switch>
    <case>
        <condition>False</condition>
        <action participant="test1" />
    </case>
    <case>
        <condition>True</condition>
        <action participant="test2" />
    </case>
</switch>
"""

class TestSwitch(unittest.TestCase):
    """Tests for Switch activity."""

    def setUp(self):
        xml_element = ET.fromstring(processdsc)
        self.fexpr = Switch('fake-id', xml_element, 'fake-id_0', Context())
        self.ch = Mock()

    def test_handle_message_completed_state(self):
        """Test Switch.handle_message() when Switch is completed."""

        msg = Message(name='start', target='fake-id_0', origin='fake-id')
        self.fexpr.state = 'completed'
        result = self.fexpr.handle_message(self.ch, msg)
        self.assertEqual(result, 'ignored')

    def test_handle_message_wrong_target(self):
        """Test Switch.handle_message() when message targeted not to it."""

        msg = Message(name='start', target='fake-id_10', origin='fake-id')
        self.fexpr.state = 'active'
        result = self.fexpr.handle_message(self.ch, msg)
        self.assertEqual(result, 'ignored')

    def test_handle_message_start(self):
        """Test Switch.handle_message() with start message."""

        msg = Message(name='start', target='fake-id_0', origin='fake-id')
        newmsg = Message(name='start', target='fake-id_0_1', origin='fake-id_0')
        self.fexpr.state = 'ready'
        with patch('bureaucrat.flowexpression.Message') as MockMessage:
            MockMessage.return_value = newmsg
            result = self.fexpr.handle_message(self.ch, msg)
            self.assertEqual(result, 'consumed')
            self.assertEqual(self.fexpr.state, 'active')
            # Make sure the second case is started
            MockMessage.assert_called_once_with(name='start',
                                                target='fake-id_0_1',
                                                origin='fake-id_0')
            self.ch.send.assert_called_once_with(newmsg)

    def test_handle_message_completed(self):
        """Test Switch.handle_message() with completed message from child."""

        msg = Message(name='completed', target='fake-id_0',
                      origin='fake-id_0_1')
        newmsg = Message(name='completed', target='fake-id',
                         origin='fake-id_0')
        self.fexpr.state = 'active'
        with patch('bureaucrat.flowexpression.Message') as MockMessage:
            MockMessage.return_value = newmsg
            result = self.fexpr.handle_message(self.ch, msg)
            self.assertEqual(result, 'consumed')
            self.assertEqual(self.fexpr.state, 'completed')
            MockMessage.assert_called_once_with(name='completed',
                                                target='fake-id',
                                                origin='fake-id_0')
            self.ch.send.assert_called_once_with(newmsg)

    def test_handle_message_response(self):
        """Test Switch.handle_message() with response message."""

        msg = Message(name='response', target='fake-id_0_1_0',
                      origin='fake-id_0_1_0')
        self.fexpr.state = 'active'
        self.fexpr.children[1].state = 'active'
        self.fexpr.children[1].children[0].state = 'active'
        result = self.fexpr.handle_message(self.ch, msg)
        self.assertEqual(result, 'consumed')
