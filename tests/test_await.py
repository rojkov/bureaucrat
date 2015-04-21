import unittest
import xml.etree.ElementTree as ET

from mock import Mock
from mock import patch

from bureaucrat.flowexpression import Await

processdsc = """<?xml version="1.0"?>
<await event="test_event">
    <condition>True</condition>
</await>
"""

class TestAwait(unittest.TestCase):
    """Tests for Await activity."""

    def setUp(self):
        """Set up SUT."""
        xml_element = ET.fromstring(processdsc)
        self.fexpr = Await('fake-id', xml_element, 'fake-id_0')
        self.wi = Mock()
        self.ch = Mock()
        self.wi.send = Mock()
        self.wi.subscribe = Mock()

    # TODO: move these two cases to a base class
    def test_handle_workitem_completed_state(self):
        """Test Await.handle_workitem() when While is completed."""

        self.fexpr.state = 'completed'
        result = self.fexpr.handle_workitem(self.ch, self.wi)
        self.assertTrue(result == 'ignored')

    def test_handle_workitem_wrong_target(self):
        """Test Await.handle_workitem() when workitem targeted not to it."""

        self.wi.target = 'fake-id_10'
        self.fexpr.state = 'active'
        result = self.fexpr.handle_workitem(self.ch, self.wi)
        self.assertTrue(result == 'ignored')

    def test_handle_workitem_start(self):
        """Test Await.handle_workitem() with 'start' message."""
        self.wi.message = 'start'
        self.wi.target = 'fake-id_0'
        self.wi.origin = 'fake-id'
        self.fexpr.state = 'ready'
        result = self.fexpr.handle_workitem(self.ch, self.wi)
        self.assertTrue(result == 'consumed')
        self.assertTrue(self.fexpr.state == 'active')
        self.wi.subscribe.assert_called_once_with(event='test_event',
                                                  target='fake-id_0')

    def test_handle_workitem_timeout(self):
        """Test Await.handle_workitem() with 'triggered' message."""

        self.wi.message = 'triggered'
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
