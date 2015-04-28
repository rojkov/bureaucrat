import unittest

import xml.etree.ElementTree as ET
from mock import Mock
from mock import patch

from bureaucrat.flowexpression import Process
from bureaucrat.context import Context
from bureaucrat.message import Message

processdsc = """<?xml version="1.0"?>
<process>
    <action participant="test1" />
    <action participant="test2" />
</process>
"""

class TestProcess(unittest.TestCase):
    """Tests for Process."""

    def setUp(self):
        xml_element = ET.fromstring(processdsc)
        self.fexpr = Process('', xml_element, 'fake-id', Context())
        self.ch = Mock()

    def test_handle_message_start(self):
        """Test Process.handle_message() with start message."""

        msg = Message(name='start', target='fake-id', origin='')
        newmsg = Message(name='start', target='fake-id_0', origin='fake-id')
        self.fexpr.state = 'ready'
        with patch('bureaucrat.flowexpression.Message') as MockMessage:
            MockMessage.return_value = newmsg
            result = self.fexpr.handle_message(self.ch, msg)
            self.assertEqual(result, 'consumed')
            self.assertEqual(self.fexpr.state, 'active')
            MockMessage.assert_called_once_with(name='start',
                                                target='fake-id_0',
                                                origin='fake-id')
            self.ch.send.assert_called_once_with(newmsg)

    def test_handle_message_completed1(self):
        """Test Process.handle_message() with completed msg from first child."""

        msg = Message(name='completed', target='fake-id', origin='fake-id_0')
        self.fexpr.state = 'active'
        newmsg = Message(name='start', target='fake-id_1', origin='fake-id')
        with patch('bureaucrat.flowexpression.Message') as MockMessage:
            MockMessage.return_value = newmsg
            result = self.fexpr.handle_message(self.ch, msg)
            self.assertEqual(result, 'consumed')
            self.assertEqual(self.fexpr.state, 'active')
            MockMessage.assert_called_once_with(name='start',
                                                target='fake-id_1',
                                                origin='fake-id')
            self.ch.send.assert_called_once_with(newmsg)

    def test_handle_message_completed2(self):
        """Test Process.handle_message() with completed msg from last child."""

        msg = Message(name='completed', target='fake-id', origin='fake-id_1')
        self.fexpr.state = 'active'
        newmsg = Message(name='completed', target='', origin='fake-id')
        with patch('bureaucrat.flowexpression.Message') as MockMessage:
            MockMessage.return_value = newmsg
            result = self.fexpr.handle_message(self.ch, msg)
            self.assertEqual(result, 'consumed')
            self.assertEqual(self.fexpr.state, 'completed')
            MockMessage.assert_called_once_with(name='completed', target='',
                                                origin='fake-id')
            self.ch.send.assert_called_once_with(newmsg)

    def test_handle_message_response(self):
        """Test Process.handle_message() with response msg for child."""

        msg = Message(name='response', target='fake-id_0', origin='fake-id_0')
        self.fexpr.state = 'active'
        self.fexpr.children[0].state = 'active'
        newmsg = Message(name='completed', target='fake-id',
                         origin='fake-id_0')
        with patch('bureaucrat.flowexpression.Message') as MockMessage:
            MockMessage.return_value = newmsg
            result = self.fexpr.handle_message(self.ch, msg)
            self.assertEqual(result, 'consumed')
            self.assertEqual(self.fexpr.state, 'active')
            MockMessage.assert_called_once_with(name='completed',
                                                target='fake-id',
                                                origin='fake-id_0')
            self.ch.send.assert_called_once_with(newmsg)
