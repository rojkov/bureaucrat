import unittest
import xml.etree.ElementTree as ET

from mock import Mock, call, patch

from bureaucrat.flowexpression import All
from bureaucrat.context import Context
from bureaucrat.message import Message

processdsc = """<?xml version="1.0"?>
<all>
    <action participant="test1" />
    <action participant="test2" />
</all>
"""

class TestAll(unittest.TestCase):
    """Tests for All activity."""

    def setUp(self):
        xml_element = ET.fromstring(processdsc)
        self.fexpr = All('fake-id', xml_element, 'fake-id_0', Context())
        self.ch = Mock()
        self.ch.send = Mock()

    def test_handle_workitem_completed_state(self):
        """Test All.handle_workitem() when While is completed."""

        self.fexpr.state = 'completed'
        result = self.fexpr.handle_workitem(
            self.ch,
            Message(name='fake', target='fake-id_0', origin='fake-id')
        )
        self.assertTrue(result == 'ignored')

    def test_handle_workitem_wrong_target(self):
        """Test All.handle_workitem() when workitem targeted not to it."""

        self.fexpr.state = 'active'
        result = self.fexpr.handle_workitem(
            self.ch,
            Message(name='start', target='fake-id_1', origin='fake-id')
        )
        self.assertTrue(result == 'ignored')

    def test_handle_workitem_response(self):
        """Test All.handle_workitem() with response event."""

        msg = Message(name='response', target='fake-id_0_0',
                      origin='fake-id_0_0')
        newmsg = Message(name='completed', target='fake-id_0',
                         origin='fake-id_0_0')
        self.fexpr.state = 'active'
        self.fexpr.children[0].state = 'active'
        with patch('bureaucrat.flowexpression.Message') as MockMessage:
            MockMessage.return_value = newmsg
            result = self.fexpr.handle_workitem(self.ch, msg)
            self.assertTrue(result == 'consumed')
            self.ch.send.assert_called_once_with(newmsg)

    def test_handle_workitem_start(self):
        """Test All.handle_workitem() with start event."""

        msg = Message(name='start', target='fake-id_0', origin='fake-id')
        self.fexpr.state = 'ready'
        msg1 = Message(name='start', target='fake-id_0_0', origin='fake-id_0')
        msg2 = Message(name='start', target='fake-id_0_1', origin='fake-id_0')
        with patch('bureaucrat.flowexpression.Message') as MockMessage:
            MockMessage.side_effect = [msg1, msg2]
            result = self.fexpr.handle_workitem(self.ch, msg)
            self.assertTrue(result == 'consumed')
            self.assertTrue(self.fexpr.state == 'active')
            expected = [
                call(msg1),
                call(msg2),
            ]
            self.assertEqual(self.ch.send.call_args_list, expected)

    def test_handle_workitem_completed_with_active_child(self):
        """Test All.handle_workitem() with completed event and active child."""

        msg = Message(name='completed', target='fake-id_0',
                      origin='fake-id_0_1')
        self.fexpr.state = 'active'
        self.fexpr.children[0].state = 'active'
        self.fexpr.children[1].state = 'completed'
        result = self.fexpr.handle_workitem(self.ch, msg)
        self.assertTrue(result == 'consumed')
        self.assertTrue(self.fexpr.state == 'active')
        self.assertTrue(self.ch.send.call_args_list == [])

    def test_handle_workitem_completed_with_completed_children(self):
        """Test All.handle_workitem() with completed workitem with no active child."""

        msg = Message(name='completed', target='fake-id_0',
                      origin='fake-id_0_1')
        newmsg = Message(name='completed', target='fake-id',
                         origin='fake-id_0')
        self.fexpr.state = 'active'
        self.fexpr.children[0].state = 'completed'
        self.fexpr.children[1].state = 'completed'
        with patch('bureaucrat.flowexpression.Message') as MockMessage:
            MockMessage.return_value = newmsg
            result = self.fexpr.handle_workitem(self.ch, msg)
            self.assertTrue(result == 'consumed')
            self.assertTrue(self.fexpr.state == 'completed')
            self.ch.send.assert_called_once_with(newmsg)
