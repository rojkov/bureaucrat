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
        self.mock_event = Mock()
        self.mock_event.trigger = Mock()

    def test_handle_event_completed_state(self):
        """Test Call.handle_event() when While is completed."""

        self.fexpr.state = 'completed'
        result = self.fexpr.handle_event(self.mock_event)
        self.assertTrue(result == 'ignored')

    def test_handle_event_wrong_target(self):
        """Test Call.handle_event() when event targeted not to it."""

        self.mock_event.target = 'fake-id_1'
        self.fexpr.state = 'active'
        result = self.fexpr.handle_event(self.mock_event)
        self.assertTrue(result == 'ignored')

    def test_handle_event_start(self):
        """Test Call.handle_event() with start event."""

        self.mock_event.name = 'start'
        self.mock_event.target = 'fake-id_0'
        self.mock_event.workitem.origin = 'fake-id'
        self.mock_event.workitem.fields = {
            "some_process_name": subprocessdsc
        }
        self.fexpr.state = 'ready'
        result = self.fexpr.handle_event(self.mock_event)
        self.assertTrue(result == 'consumed')
        self.assertTrue(self.fexpr.state == 'active')
        # TODO: assert that process launch event was sent to dispatcher

    def test_handle_event_completed(self):
        """Test Call.handle_event() with completed event."""

        self.mock_event.name = 'completed'
        self.mock_event.target = 'fake-id_0'
        self.mock_event.workitem.origin = 'other-fake-id'
        self.mock_event.workitem.fields = {}
        self.fexpr.state = 'active'
        result = self.fexpr.handle_event(self.mock_event)
        self.assertTrue(result == 'consumed')
        self.assertTrue(self.fexpr.state == 'completed')
        self.mock_event.trigger.assert_called_once_with()
        # TODO: assert completed event was sent to parent
