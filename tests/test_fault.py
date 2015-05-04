from __future__ import absolute_import

import unittest
import xml.etree.ElementTree as ET

from mock import Mock
from mock import patch

from bureaucrat.flowexpression import Process
from bureaucrat.context import Context
from bureaucrat.message import Message

procdsc = """
<process>
    <action participant="test1" />
    <fault />
    <action participant="test2" />
    <fault code="SomeError" message="Some text" />
</process>
"""

class TestFault(unittest.TestCase):
    """Tests for the Fault activity."""

    def setUp(self):
        """Set up test case."""

        xmlelement = ET.fromstring(procdsc)
        self.root = Process('', xmlelement, 'fake-id', Context())
        self.root.state = 'active'
        self.root.children[0].state = 'active'
        self.ch = Mock()

    def test_handle_message_start(self):
        """Test handling message 'start'."""
        msg = Message(name='start', target='fake-id_1', origin='fake-id')
        with patch('bureaucrat.flowexpression.Message') as MockMsg:
            newmsg = Message(name='fault', target='fake-id',
                             origin='fake-id_1',
                             payload={
                                 "code": "terminate",
                                 "message": ""
                             })
            MockMsg.return_value = newmsg
            result = self.root.handle_message(self.ch, msg)
            self.assertEqual(result, 'consumed')
            MockMsg.assert_called_once_with(name='fault', target='fake-id',
                                            origin='fake-id_1',
                                            payload={
                                                "code": "terminate",
                                                "message": ""
                                            })
            self.ch.send.assert_called_once_with(newmsg)
            self.assertEqual(self.root.children[1].state, "completed")

    def test_handle_message_start_return_code(self):
        """Test handling message 'start'. Expect custom error code."""
        msg = Message(name='start', target='fake-id_3', origin='fake-id')
        with patch('bureaucrat.flowexpression.Message') as MockMsg:
            newmsg = Message(name='fault', target='fake-id',
                             origin='fake-id_3',
                             payload={
                                 "code": "SomeError",
                                 "message": "Some text"
                             })
            MockMsg.return_value = newmsg
            result = self.root.handle_message(self.ch, msg)
            self.assertEqual(result, 'consumed')
            MockMsg.assert_called_once_with(name='fault', target='fake-id',
                                            origin='fake-id_3',
                                            payload={
                                                "code": "SomeError",
                                                "message": "Some text"
                                            })
            self.ch.send.assert_called_once_with(newmsg)
            self.assertEqual(self.root.children[3].state, "completed")
