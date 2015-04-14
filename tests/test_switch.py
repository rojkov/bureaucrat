import unittest

import xml.etree.ElementTree as ET
from mock import Mock

from bureaucrat.flowexpression import Switch

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
        self.fexpr = Switch('fake-id', xml_element, 'fake-id_0')
        self.ch = Mock()
        self.wi = Mock()
        self.wi.send = Mock()

    def test_handle_workitem_completed_state(self):
        """Test Switch.handle_workitem() when Switch is completed."""

        self.fexpr.state = 'completed'
        result = self.fexpr.handle_workitem(self.ch, self.wi)
        self.assertTrue(result == 'ignored')

    def test_handle_workitem_wrong_target(self):
        """Test Switch.handle_workitem() when workitem targeted not to it."""

        self.wi.target = 'fake-id_1'
        self.fexpr.state = 'active'
        result = self.fexpr.handle_workitem(self.ch, self.wi)
        self.assertTrue(result == 'ignored')

    def test_handle_workitem_start(self):
        """Test Switch.handle_workitem() with start message."""

        self.wi.message = 'start'
        self.wi.target = 'fake-id_0'
        self.wi.origin = ''
        self.fexpr.state = 'ready'
        result = self.fexpr.handle_workitem(self.ch, self.wi)
        self.assertTrue(result == 'consumed')
        self.assertTrue(self.fexpr.state == 'active')
        # Make sure the second case is started
        self.wi.send.assert_called_once_with(self.ch, message='start',
                                             target='fake-id_0_1',
                                             origin='fake-id_0')

    def test_handle_workitem_completed(self):
        """Test Switch.handle_workitem() with completed message from child."""

        self.wi.message = 'completed'
        self.wi.target = 'fake-id_0'
        self.wi.origin = 'fake-id_0_1'
        self.fexpr.state = 'active'
        result = self.fexpr.handle_workitem(self.ch, self.wi)
        self.assertTrue(result == 'consumed')
        self.assertTrue(self.fexpr.state == 'completed')
        self.wi.send.assert_called_once_with(self.ch, message='completed',
                                             target='fake-id',
                                             origin='fake-id_0')

    def test_handle_workitem_response(self):
        """Test Switch.handle_workitem() with response workitem."""

        self.wi.message = 'response'
        self.wi.target = 'fake-id_0_1_0'
        self.wi.origin = 'fake-id_0_1_0'
        self.fexpr.state = 'active'
        self.fexpr.children[1].state = 'active'
        self.fexpr.children[1].children[0].state = 'active'
        result = self.fexpr.handle_workitem(self.ch, self.wi)
        self.assertTrue(result == 'consumed')
