import unittest
import xml.etree.ElementTree as ET
from mock import Mock

from bureaucrat.flowexpression import While

processdsc_true = """<?xml version="1.0"?>
<while>
    <condition>True</condition>
    <action participant="test1" />
    <action participant="test2" />
</while>
"""

processdsc_false = """<?xml version="1.0"?>
<while>
    <condition>False</condition>
    <action participant="test1" />
    <action participant="test2" />
</while>
"""

class TestWhile(unittest.TestCase):
    """Tests for While activity."""

    processdsc = processdsc_true

    def setUp(self):
        xml_element = ET.fromstring(self.processdsc)
        self.fexpr = While('fake-id', xml_element, 'fake-id_0')
        self.ch = Mock()
        self.wi = Mock()
        self.wi.send = Mock()

    def test_handle_workitem_completed_state(self):
        """Test While.handle_workitem() when While is completed."""

        self.fexpr.state = 'completed'
        result = self.fexpr.handle_workitem(self.ch, self.wi)
        self.assertTrue(result == 'ignored')

    def test_handle_workitem_wrong_target(self):
        """Test While.handle_workitem() when workitem targeted not to it."""

        self.wi.target = 'fake-id_1'
        self.fexpr.state = 'active'
        result = self.fexpr.handle_workitem(self.ch, self.wi)
        self.assertTrue(result == 'ignored')

    def test_handle_workitem_response(self):
        """Test While.handle_workitem() with response workitem."""

        self.wi.message = 'response'
        self.wi.target = 'fake-id_0_0'
        self.wi.origin = 'fake-id_0_0'
        self.fexpr.state = 'active'
        self.fexpr.children[0].state = 'active'
        result = self.fexpr.handle_workitem(self.ch, self.wi)
        self.assertTrue(result == 'consumed')

    def test_handle_workitem_completed_not_last(self):
        """Test While.handle_workitem() with completed msg from first child."""

        self.wi.message = 'completed'
        self.wi.target = 'fake-id_0'
        self.wi.origin = 'fake-id_0_0'
        self.fexpr.state = 'active'
        result = self.fexpr.handle_workitem(self.ch, self.wi)
        self.assertTrue(result == 'consumed')
        self.wi.send.assert_called_once_with(self.ch, message='start',
                                             target='fake-id_0_1',
                                             origin='fake-id_0')

class TestWhileTrueCondition(TestWhile):
    """Tests for While with conditions evaluated to True."""

    processdsc = processdsc_true

    def test_handle_workitem_start(self):
        """Test While.handle_workitem() with start event."""

        self.wi.message = 'start'
        self.wi.target = 'fake-id_0'
        self.wi.origin = ''
        self.fexpr.state = 'ready'
        result = self.fexpr.handle_workitem(self.ch, self.wi)
        self.assertTrue(result == 'consumed')
        self.assertTrue(self.fexpr.state == 'active')
        self.wi.send.assert_called_once_with(self.ch, message='start',
                                             target='fake-id_0_0',
                                             origin='fake-id_0')

    def test_handle_workitem_completed_last(self):
        """Test While.handle_workitem() with completed event from last child."""

        self.wi.message = 'completed'
        self.wi.target = 'fake-id_0'
        self.wi.origin = 'fake-id_0_1'
        self.fexpr.state = 'active'
        result = self.fexpr.handle_workitem(self.ch, self.wi)
        self.assertTrue(result == 'consumed')
        self.assertTrue(self.fexpr.state == 'active')
        self.wi.send.assert_called_once_with(self.ch, message='start',
                                             target='fake-id_0_0',
                                             origin='fake-id_0')

class TestWhileFalseCondition(TestWhile):
    """Tests for While with conditions evaluated to False."""

    processdsc = processdsc_false

    def test_handle_workitem_start(self):
        """Test While.handle_workitem() with start event."""

        self.wi.message = 'start'
        self.wi.target = 'fake-id_0'
        self.wi.origin = 'fake-id'
        self.fexpr.state = 'ready'
        result = self.fexpr.handle_workitem(self.ch, self.wi)
        self.assertTrue(result == 'consumed')
        self.assertTrue(self.fexpr.state == 'completed')
        self.wi.send.assert_called_once_with(self.ch, message='completed',
                                             target='fake-id',
                                             origin='fake-id_0')

    def test_handle_workitem_completed_last(self):
        """Test While.handle_workitem() with completed event from last child."""

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
