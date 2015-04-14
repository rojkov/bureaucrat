import unittest
import xml.etree.ElementTree as ET

from mock import Mock, call, patch

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
        self.ch = Mock()
        self.wi = Mock()
        self.wi.send = Mock()

    def test_handle_workitem_completed_state(self):
        """Test All.handle_workitem() when While is completed."""

        self.fexpr.state = 'completed'
        result = self.fexpr.handle_workitem(self.ch, self.wi)
        self.assertTrue(result == 'ignored')

    def test_handle_workitem_wrong_target(self):
        """Test All.handle_workitem() when workitem targeted not to it."""

        self.wi.target = 'fake-id_1'
        self.fexpr.state = 'active'
        result = self.fexpr.handle_workitem(self.ch, self.wi)
        self.assertTrue(result == 'ignored')

    def test_handle_workitem_response(self):
        """Test All.handle_workitem() with response event."""

        self.wi.message = 'response'
        self.wi.target = 'fake-id_0_0'
        self.wi.origin = 'fake-id_0_0'
        self.fexpr.state = 'active'
        self.fexpr.children[0].state = 'active'
        result = self.fexpr.handle_workitem(self.ch, self.wi)
        self.assertTrue(result == 'consumed')
        self.wi.send.assert_called_once_with(self.ch, message='completed',
                                             origin='fake-id_0_0',
                                             target='fake-id_0')

    def test_handle_workitem_start(self):
        """Test All.handle_workitem() with start event."""

        self.wi.message = 'start'
        self.wi.target = 'fake-id_0'
        self.wi.origin = 'fake-id'
        self.fexpr.state = 'ready'
        result = self.fexpr.handle_workitem(self.ch, self.wi)
        self.assertTrue(result == 'consumed')
        self.assertTrue(self.fexpr.state == 'active')
        expected = [
            call(self.ch, message='start', origin='fake-id_0',
                 target='fake-id_0_0'),
            call(self.ch, message='start', origin='fake-id_0',
                 target='fake-id_0_1'),
        ]
        self.assertTrue(self.wi.send.call_args_list == expected)

    def test_handle_workitem_completed_with_active_child(self):
        """Test All.handle_workitem() with completed event and active child."""

        self.wi.message = 'completed'
        self.wi.target = 'fake-id_0'
        self.wi.origin = 'fake-id_0_1'
        self.wi.fields = {}
        self.fexpr.state = 'active'
        self.fexpr.context = {}
        self.fexpr.children[0].state = 'active'
        self.fexpr.children[1].state = 'completed'
        result = self.fexpr.handle_workitem(self.ch, self.wi)
        self.assertTrue(result == 'consumed')
        self.assertTrue(self.fexpr.state == 'active')
        self.assertTrue(self.wi.send.call_args_list == [])

    def test_handle_workitem_completed_with_completed_children(self):
        """Test All.handle_workitem() with completed workitem with no active child."""

        self.wi.message = 'completed'
        self.wi.target = 'fake-id_0'
        self.wi.origin = 'fake-id_0_1'
        self.wi.fields = {}
        self.fexpr.state = 'active'
        self.fexpr.context = {}
        self.fexpr.children[0].state = 'completed'
        self.fexpr.children[1].state = 'completed'
        with patch('bureaucrat.flowexpression.Workitem') as mock_wiclass:
            mock_wi = Mock()
            mock_wiclass.return_value = mock_wi
            result = self.fexpr.handle_workitem(self.ch, self.wi)
            self.assertTrue(result == 'consumed')
            self.assertTrue(self.fexpr.state == 'completed')
            mock_wiclass.assert_called_once()
            mock_wi.send.assert_called_once_with(self.ch, message='completed',
                                                 origin='fake-id_0',
                                                 target='fake-id')
