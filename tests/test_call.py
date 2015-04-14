import unittest
import xml.etree.ElementTree as ET

from mock import Mock

from bureaucrat.flowexpression import Call

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
        self.fexpr = Call('fake-id', xml_element, 'fake-id_0')
        self.wi = Mock()
        self.ch = Mock()
        self.wi.send = Mock()

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
        """Test Call.handle_workitem() with 'start' message."""

        self.wi.message = 'start'
        self.wi.target = 'fake-id_0'
        self.wi.origin = 'fake-id'
        self.wi.fields = {
            "some_process_name": subprocessdsc
        }
        self.fexpr.state = 'ready'
        result = self.fexpr.handle_workitem(self.ch, self.wi)
        self.assertTrue(result == 'consumed')
        self.assertTrue(self.fexpr.state == 'active')
        # TODO: assert that process launch event was sent to dispatcher

    def test_handle_workitem_completed(self):
        """Test Call.handle_workitem() with 'completed' message."""

        self.wi.message = 'completed'
        self.wi.target = 'fake-id_0'
        self.wi.origin = 'other-fake-id'
        self.wi.fields = {}
        self.fexpr.state = 'active'
        result = self.fexpr.handle_workitem(self.ch, self.wi)
        self.assertTrue(result == 'consumed')
        self.assertTrue(self.fexpr.state == 'completed')
        self.wi.send.assert_called_once_with(self.ch, message='completed',
                                             origin='fake-id_0',
                                             target='fake-id')
