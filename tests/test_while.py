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

processdsc_empty = """<?xml version="1.0"?>
<while>
    <condition>True</condition>
</while>
"""

class TestWhile(unittest.TestCase):

    processdsc = processdsc_true

    def setUp(self):
        xml_element = ET.fromstring(self.processdsc)
        self.fexpr = While('', xml_element, '0')
        self.mock_event = Mock()
        self.mock_event.trigger = Mock()

    def test_handle_event_completed_state(self):
        """Test While.handle_event() when While is completed."""

        self.fexpr.state = 'completed'
        result = self.fexpr.handle_event(self.mock_event)
        self.assertTrue(result == 'ignored')

    def test_handle_event_wrong_target(self):
        """Test While.handle_event() when event targeted not to it."""

        self.mock_event.target = '1'
        self.fexpr.state = 'active'
        result = self.fexpr.handle_event(self.mock_event)
        self.assertTrue(result == 'ignored')

    def test_handle_event_response(self):
        """Test While.handle_event() with response event."""

        self.mock_event.name = 'response'
        self.mock_event.target = '0_0'
        self.mock_event.workitem.origin = '0_0'
        self.fexpr.state = 'active'
        self.fexpr.children[0].state = 'active'
        result = self.fexpr.handle_event(self.mock_event)
        self.assertTrue(result == 'consumed')

    def test_handle_event_completed_not_last(self):
        """Test While.handle_event() with completed event from first child."""

        self.mock_event.name = 'completed'
        self.mock_event.target = '0'
        self.mock_event.workitem.origin = '0_0'
        self.fexpr.state = 'active'
        result = self.fexpr.handle_event(self.mock_event)
        self.assertTrue(result == 'consumed')
        self.assertTrue(self.mock_event.target == '0_1')
        self.assertTrue(self.mock_event.workitem.origin == '0')
        self.assertTrue(self.mock_event.workitem.event_name == 'start')
        self.mock_event.trigger.assert_called_once_with()

class TestWhileTrueCondition(TestWhile):
    """Tests for While with conditions evaluated to True."""

    processdsc = processdsc_true

    def test_handle_event_start(self):
        """Test While.handle_event() with start event."""

        self.mock_event.name = 'start'
        self.mock_event.target = '0'
        self.mock_event.workitem.origin = ''
        self.fexpr.state = 'ready'
        result = self.fexpr.handle_event(self.mock_event)
        self.assertTrue(result == 'consumed')
        self.assertTrue(self.mock_event.target == '0_0')
        self.mock_event.trigger.assert_called_once_with()
        self.assertTrue(self.fexpr.state == 'active')

    def test_handle_event_completed_last(self):
        """Test While.handle_event() with completed event from last child."""

        self.mock_event.name = 'completed'
        self.mock_event.target = '0'
        self.mock_event.workitem.origin = '0_1'
        self.fexpr.state = 'active'
        result = self.fexpr.handle_event(self.mock_event)
        self.assertTrue(result == 'consumed')
        self.assertTrue(self.fexpr.state == 'active')
        self.assertTrue(self.mock_event.target == '0_0')
        self.assertTrue(self.mock_event.workitem.origin == '0')
        self.assertTrue(self.mock_event.workitem.event_name == 'start')
        self.mock_event.trigger.assert_called_once_with()

class TestWhileFalseCondition(TestWhile):
    """Tests for While with conditions evaluated to False."""

    processdsc = processdsc_false

    def test_handle_event_start(self):
        """Test While.handle_event() with start event."""

        self.mock_event.name = 'start'
        self.mock_event.target = '0'
        self.mock_event.workitem.origin = ''
        self.fexpr.state = 'ready'
        result = self.fexpr.handle_event(self.mock_event)
        self.assertTrue(result == 'consumed')
        self.assertTrue(self.mock_event.target == '')
        self.mock_event.trigger.assert_called_once_with()
        self.assertTrue(self.fexpr.state == 'completed')

    def test_handle_event_completed_last(self):
        """Test While.handle_event() with completed event from last child."""

        self.mock_event.name = 'completed'
        self.mock_event.target = '0'
        self.mock_event.workitem.origin = '0_1'
        self.fexpr.state = 'active'
        result = self.fexpr.handle_event(self.mock_event)
        self.assertTrue(result == 'consumed')
        self.assertTrue(self.fexpr.state == 'completed')
        self.mock_event.trigger.assert_called_once_with()
