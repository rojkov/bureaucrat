import unittest

import xml.etree.ElementTree as ET
from mock import Mock

from bureaucrat.flowexpression import Process

processdsc = """<?xml version="1.0"?>
<process>
    <action participant="test1" />
    <action participant="test2" />
</process>
"""

class TestProcess(unittest.TestCase):
    """Tests for Process."""

    def setUp(self):
        xml_element = ET.fromstring(processdsc)
        self.fexpr = Process('', xml_element, 'fake-id')
        self.ch = Mock()
        self.wi = Mock()
        self.wi.send = Mock()

    def test_handle_workitem_start(self):
        """Test Process.handle_workitem() with start message."""

        self.wi.message = 'start'
        self.wi.target = 'fake-id'
        self.wi.origin = ''
        self.fexpr.state = 'ready'
        result = self.fexpr.handle_workitem(self.ch, self.wi)
        self.assertTrue(result == 'consumed')
        self.assertTrue(self.fexpr.state == 'active')
        self.wi.send.assert_called_once_with(self.ch, message='start',
                                             target='fake-id_0',
                                             origin='fake-id')

    def test_handle_workitem_completed1(self):
        """Test Process.handle_workitem() with completed msg from first child."""

        self.wi.message = 'completed'
        self.wi.target = 'fake-id'
        self.wi.origin = 'fake-id_0'
        self.fexpr.state = 'active'
        result = self.fexpr.handle_workitem(self.ch, self.wi)
        self.assertTrue(result == 'consumed')
        self.assertTrue(self.fexpr.state == 'active')
        self.wi.send.assert_called_once_with(self.ch, message='start',
                                             target='fake-id_1',
                                             origin='fake-id')

    def test_handle_workitem_completed2(self):
        """Test Process.handle_workitem() with completed msg from last child."""

        self.wi.message = 'completed'
        self.wi.target = 'fake-id'
        self.wi.origin = 'fake-id_1'
        self.fexpr.state = 'active'
        result = self.fexpr.handle_workitem(self.ch, self.wi)
        self.assertTrue(result == 'consumed')
        self.assertTrue(self.fexpr.state == 'completed')
        self.wi.send.assert_called_once_with(self.ch, message='completed',
                                             target='',
                                             origin='fake-id')

    def test_handle_workitem_response(self):
        """Test Process.handle_workitem() with response msg for child."""

        self.wi.message = 'response'
        self.wi.target = 'fake-id_0'
        self.wi.origin = 'fake-id_0'
        self.fexpr.state = 'active'
        self.fexpr.children[0].state = 'active'
        result = self.fexpr.handle_workitem(self.ch, self.wi)
        self.assertTrue(result == 'consumed')
        self.assertTrue(self.fexpr.state == 'active')
        self.wi.send.assert_called_once_with(self.ch, message='completed',
                                             target='fake-id',
                                             origin='fake-id_0')
