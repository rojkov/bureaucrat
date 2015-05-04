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
    <context>
        <property name="prop1" type="int">0</property>
        <property name="prop2" type="int">3</property>
    </context>
    <assign property="prop1">context["prop2"] + 4</assign>
</process>
"""

class TestAssign(unittest.TestCase):
    """Tests for Assign activity."""

    def setUp(self):
        """Set up test case."""

        xmlelement = ET.fromstring(procdsc)
        self.root = Process('', xmlelement, 'fake-id', Context())
        self.root.state = 'active'
        self.ch = Mock()

    def test_handle_message_start(self):
        """Test handling message 'start'."""
        msg = Message(name='start', target='fake-id_0', origin='fake-id')
        with patch('bureaucrat.flowexpression.Message') as MockMsg:
            newmsg = Message(name='completed', target='fake-id',
                             origin='fake-id_0')
            MockMsg.return_value = newmsg
            result = self.root.handle_message(self.ch, msg)
            self.assertEqual(result, 'consumed')
            MockMsg.assert_called_once_with(name='completed', target='fake-id',
                                            origin='fake-id_0')
            self.ch.send.assert_called_once_with(newmsg)
            self.assertEqual(self.root.children[0].state, "completed")
            self.assertEqual(self.root.context.get("prop1"), 7)
