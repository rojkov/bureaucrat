import unittest
import xml.etree.ElementTree as ET

from mock import Mock
from mock import patch

from bureaucrat.flowexpression import Delay
from bureaucrat.context import Context
from bureaucrat.message import Message

processdsc = """<?xml version="1.0"?>
<delay duration="120" />
"""

class TestDelay(unittest.TestCase):
    """Tests for Delay activity."""

    def setUp(self):
        """Set up SUT."""
        xml_element = ET.fromstring(processdsc)
        self.fexpr = Delay('fake-id', xml_element, 'fake-id_0', Context())
        self.ch = Mock()

    # TODO: move these two cases to a base class
    def test_handle_workitem_completed_state(self):
        """Test Delay.handle_workitem() when Delay is completed."""

        msg = Message(name='start', target='fake-id_0', origin='fake-id')
        self.fexpr.state = 'completed'
        result = self.fexpr.handle_workitem(self.ch, msg)
        self.assertEqual(result, 'ignored')

    def test_handle_workitem_wrong_target(self):
        """Test Delay.handle_workitem() when message targeted not to it."""

        msg = Message(name='start', target='fake-id_10', origin='fake-id')
        self.fexpr.state = 'active'
        result = self.fexpr.handle_workitem(self.ch, msg)
        self.assertEqual(result, 'ignored')

    def test_handle_workitem_start(self):
        """Test Delay.handle_workitem() with 'start' message."""
        msg = Message(name='start', target='fake-id_0', origin='fake-id')
        self.fexpr.state = 'ready'
        with patch('bureaucrat.flowexpression.time.time') as mock_time:
            mock_time.return_value = 10000
            result = self.fexpr.handle_workitem(self.ch, msg)
            self.assertEqual(result, 'consumed')
            self.assertEqual(self.fexpr.state, 'active')
            self.ch.schedule_event.assert_called_once_with(code='timeout',
                                                           instant=10120,
                                                           target='fake-id_0')

    def test_handle_workitem_timeout(self):
        """Test Delay.handle_workitem() with 'timeout' message."""

        msg = Message(name='timeout', target='fake-id_0', origin='fake-id_0')
        newmsg = Message(name='completed', target='fake-id', origin='fake-id_0')
        self.fexpr.state = 'active'
        with patch('bureaucrat.flowexpression.Message') as MockMessage:
            MockMessage.return_value = newmsg
            result = self.fexpr.handle_workitem(self.ch, msg)
            self.assertEqual(result, 'consumed')
            self.assertEqual(self.fexpr.state, 'completed')
            MockMessage.assert_called_once_with(name='completed',
                                                target='fake-id',
                                                origin='fake-id_0')
            self.ch.send.assert_called_once_with(newmsg)
