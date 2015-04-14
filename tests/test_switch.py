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
