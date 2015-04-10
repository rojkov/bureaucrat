import unittest
import xml.etree.ElementTree as ET

from mock import Mock

from bureaucrat.flowexpression import All

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
        self.fexpr = All('fake-id', xml_element, 'fake-id_0')
        self.mock_event = Mock()
        self.mock_event.trigger = Mock()

    def test_handle_event_completed_state(self):
        """Test All.handle_event() when While is completed."""

        self.fexpr.state = 'completed'
        result = self.fexpr.handle_event(self.mock_event)
        self.assertTrue(result == 'ignored')

    def test_handle_event_wrong_target(self):
        """Test All.handle_event() when event targeted not to it."""

        self.mock_event.target = 'fake-id_1'
        self.fexpr.state = 'active'
        result = self.fexpr.handle_event(self.mock_event)
        self.assertTrue(result == 'ignored')

    def test_handle_event_response(self):
        """Test All.handle_event() with response event."""

        self.mock_event.name = 'response'
        self.mock_event.target = 'fake-id_0_0'
        self.mock_event.workitem.origin = 'fake-id_0_0'
        self.fexpr.state = 'active'
        self.fexpr.children[0].state = 'active'
        result = self.fexpr.handle_event(self.mock_event)
        self.assertTrue(result == 'consumed')

    def test_handle_event_start(self):
        """Test All.handle_event() with start event."""

        self.mock_event.name = 'start'
        self.mock_event.target = 'fake-id_0'
        self.mock_event.workitem.origin = 'fake-id'
        self.fexpr.state = 'ready'
        result = self.fexpr.handle_event(self.mock_event)
        self.assertTrue(result == 'consumed')
        self.assertTrue(self.fexpr.state == 'active')
        # TODO: assert start events were sent to all children

    def test_handle_event_completed_with_active_child(self):
        """Test All.handle_event() with completed event and an active child."""

        self.mock_event.name = 'completed'
        self.mock_event.target = 'fake-id_0'
        self.mock_event.workitem.origin = 'fake-id_0_1'
        self.mock_event.workitem.fields = {}
        self.fexpr.state = 'active'
        self.fexpr.context = {}
        self.fexpr.children[0].state = 'active'
        self.fexpr.children[1].state = 'completed'
        result = self.fexpr.handle_event(self.mock_event)
        self.assertTrue(result == 'consumed')
        self.assertTrue(self.fexpr.state == 'active')

    def test_handle_event_completed_with_completed_children(self):
        """Test All.handle_event() with completed event with no active child."""

        self.mock_event.name = 'completed'
        self.mock_event.target = 'fake-id_0'
        self.mock_event.workitem.origin = 'fake-id_0_1'
        self.mock_event.workitem.fields = {}
        self.fexpr.state = 'active'
        self.fexpr.context = {}
        self.fexpr.children[0].state = 'completed'
        self.fexpr.children[1].state = 'completed'
        result = self.fexpr.handle_event(self.mock_event)
        self.assertTrue(result == 'consumed')
        self.assertTrue(self.fexpr.state == 'completed')
        # TODO: assert completed event was sent to parent
