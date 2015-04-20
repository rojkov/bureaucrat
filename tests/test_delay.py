import unittest
import xml.etree.ElementTree as ET

from mock import Mock
from mock import patch

from bureaucrat.flowexpression import Delay

processdsc = """<?xml version="1.0"?>
<delay duration="120" />
"""

class TestDelay(unittest.TestCase):
    """Tests for Delay activity."""

    def setUp(self):
        """Set up SUT."""
        xml_element = ET.fromstring(processdsc)
        self.fexpr = Delay('fake-id', xml_element, 'fake-id_0')
        self.wi = Mock()
        self.ch = Mock()
        self.wi.send = Mock()
        self.wi.schedule_event = Mock()

    # TODO: move these two cases to a base class
    def test_handle_workitem_completed_state(self):
        """Test Call.handle_workitem() when While is completed."""

        self.fexpr.state = 'completed'
        result = self.fexpr.handle_workitem(self.ch, self.wi)
        self.assertTrue(result == 'ignored')

    def test_handle_workitem_wrong_target(self):
        """Test Call.handle_workitem() when workitem targeted not to it."""

        self.wi.target = 'fake-id_1'
        self.fexpr.state = 'active'
        result = self.fexpr.handle_workitem(self.ch, self.wi)
        self.assertTrue(result == 'ignored')

    def test_handle_workitem_start(self):
        """Test Delay.handle_workitem() with 'start' message."""
        self.wi.message = 'start'
        self.wi.target = 'fake-id_0'
        self.wi.origin = 'fake-id'
        self.fexpr.state = 'ready'
        with patch('bureaucrat.flowexpression.time.time') as mock_time:
            mock_time.return_value = 10000
            result = self.fexpr.handle_workitem(self.ch, self.wi)
            self.assertTrue(result == 'consumed')
            self.assertTrue(self.fexpr.state == 'active')
            self.wi.schedule_event.assert_called_once_with(self.ch,
                                                           code='timeout',
                                                           instant=10120,
                                                           target='fake-id_0')

    def test_handle_workitem_timeout(self):
        """Test Delay.handle_workitem() with 'timeout' message."""

        self.wi.message = 'timeout'
        self.wi.target = 'fake-id_0'
        self.wi.origin = 'fake-id_0'
        self.wi.fields = {}
        self.fexpr.state = 'active'
        result = self.fexpr.handle_workitem(self.ch, self.wi)
        self.assertTrue(result == 'consumed')
        self.assertTrue(self.fexpr.state == 'completed')
        self.wi.send.assert_called_once_with(self.ch, message='completed',
                                             origin='fake-id_0',
                                             target='fake-id')
