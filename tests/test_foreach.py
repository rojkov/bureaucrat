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
        <property name="prop1" type="int">1</property>
        <property name="prop2" type="json">{"subkey": ["one", "two"]}</property>
    </context>
    <foreach select="prop2.subkey">
        <context>
            <property name="prop2" type="int">2</property>
            <property name="prop3" type="int">2</property>
        </context>
        <action participant="p1" />
        <action participant="p2" />
    </foreach>
</process>
"""

class TestForeach(unittest.TestCase):
    """Tests for Foreach activity."""

    def setUp(self):
        """Set up test case."""
        xml_element = ET.fromstring(procdsc)
        self.root = Process('', xml_element, 'fake-id', Context())
        self.foreach = self.root.children[0]
        self.ch = Mock()

    def test_handle_message_completed_state(self):
        """Test Foreach.handle_message() when Foreach is completed."""

        msg = Message(name='start', target='fake-id_0', origin='fake-id')
        self.root.state = 'active'
        self.foreach.state = 'completed'
        result = self.root.handle_message(self.ch, msg)
        self.assertEqual(result, 'ignored')

    def test_handle_message_wrong_target(self):
        """Test Foreach.handle_message() when message targeted not to it."""

        msg = Message(name='start', target='fake-id_10', origin='fake-id')
        self.root.state = 'active'
        self.foreach.state = 'active'
        result = self.root.handle_message(self.ch, msg)
        self.assertEqual(result, 'ignored')

    def test_handle_message_start_with_empty_select(self):
        """Test Foreach.handle_message() with start msg and empty select."""

        msg = Message(name='start', target='fake-id_0', origin='fake-id')
        self.root.state = 'active'
        self.root.context.set('prop2', {"subkey": []})
        with patch('bureaucrat.flowexpression.Message') as MockMessage:
            newmsg = Message(name='completed', target='fake-id',
                             origin='fake-id_0')
            MockMessage.return_value = newmsg
            result = self.root.handle_message(self.ch, msg)
            self.assertEqual(result, 'consumed')
            self.assertEqual(self.foreach.state, 'completed')
            MockMessage.assert_called_once_with(name='completed',
                                                target='fake-id',
                                                origin='fake-id_0')
            self.ch.send.assert_called_once_with(newmsg)

    def test_handle_message_start(self):
        """Test Foreach.handle_message() with start msg."""

        msg = Message(name='start', target='fake-id_0', origin='fake-id')
        self.root.state = 'active'
        with patch('bureaucrat.flowexpression.Message') as MockMessage:
            newmsg = Message(name='start', target='fake-id_0_0',
                             origin='fake-id_0')
            MockMessage.return_value = newmsg
            result = self.root.handle_message(self.ch, msg)
            self.assertEqual(result, 'consumed')
            self.assertEqual(self.foreach.state, 'active')
            MockMessage.assert_called_once_with(name='start',
                                                target='fake-id_0_0',
                                                origin='fake-id_0')
            self.ch.send.assert_called_once_with(newmsg)
            self.assertEqual(self.foreach.context.get('inst:iteration'), 1)
            self.assertEqual(self.foreach.context.get('inst:current'), 'one')

    def test_handle_message_completed_from_non_last_child(self):
        """Test Foreach.handle_message() with complete msg from non last child.
        """

        msg = Message(name='completed', target='fake-id_0',
                      origin='fake-id_0_0')
        self.root.state = 'active'
        self.foreach.state = 'active'
        self.foreach.context._props["inst:iteration"] = 1
        self.foreach.context._props["inst:selection"] = ["one", "two"]
        with patch('bureaucrat.flowexpression.Message') as MockMessage:
            newmsg = Message(name='start', target='fake-id_0_1',
                             origin='fake-id_0')
            MockMessage.return_value = newmsg
            result = self.root.handle_message(self.ch, msg)
            self.assertEqual(result, 'consumed')
            self.assertEqual(self.foreach.state, 'active')
            MockMessage.assert_called_once_with(name='start',
                                                target='fake-id_0_1',
                                                origin='fake-id_0')
            self.ch.send.assert_called_once_with(newmsg)
            self.assertEqual(self.foreach.context.get('inst:iteration'), 1)
            self.assertEqual(self.root.context.get("prop2"),
                             {"subkey": ["one", "two"]})
            self.assertEqual(self.foreach.context.get("prop2"), 2)

    def test_handle_message_completed_from_last_child(self):
        """Test Foreach.handle_message() with complete msg from last child."""

        msg = Message(name='completed', target='fake-id_0',
                      origin='fake-id_0_1')
        self.root.state = 'active'
        self.foreach.state = 'active'
        self.foreach.children[0].state = 'completed'
        self.foreach.context._props["inst:iteration"] = 1
        self.foreach.context._props["inst:current"] = "one"
        self.foreach.context._props["inst:selection"] = ["one", "two"]
        self.foreach.context.set("prop2", 10)
        self.foreach.context.set("prop3", 10)
        with patch('bureaucrat.flowexpression.Message') as MockMessage:
            newmsg = Message(name='start', target='fake-id_0_1',
                             origin='fake-id_0')
            MockMessage.return_value = newmsg
            result = self.root.handle_message(self.ch, msg)
            self.assertEqual(result, 'consumed')
            self.assertEqual(self.foreach.state, 'active')
            MockMessage.assert_called_once_with(name='start',
                                                target='fake-id_0_0',
                                                origin='fake-id_0')
            self.ch.send.assert_called_once_with(newmsg)
            self.assertEqual(self.foreach.context.get('inst:iteration'), 2)
            self.assertEqual(self.foreach.context.get('inst:current'), 'two')
            self.assertEqual(self.root.context.get("prop2"),
                             {"subkey": ["one", "two"]})
            self.assertEqual(self.foreach.context.get("prop2"), 2)
            self.assertEqual(self.foreach.context.get("prop3"), 2)

    def test_handle_message_last_completed(self):
        """Test Foreach.handle_message() with last complete msg."""

        msg = Message(name='completed', target='fake-id_0',
                      origin='fake-id_0_1')
        self.root.state = 'active'
        self.foreach.state = 'active'
        self.foreach.children[0].state = 'completed'
        self.foreach.children[1].state = 'completed'
        self.foreach.context._props["inst:iteration"] = 2
        self.foreach.context._props["inst:selection"] = ["one", "two"]
        with patch('bureaucrat.flowexpression.Message') as MockMessage:
            newmsg = Message(name='completed', target='fake-id',
                             origin='fake-id_0')
            MockMessage.return_value = newmsg
            result = self.root.handle_message(self.ch, msg)
            self.assertEqual(result, 'consumed')
            self.assertEqual(self.foreach.state, 'completed')
            MockMessage.assert_called_once_with(name='completed',
                                                target='fake-id',
                                                origin='fake-id_0')
            self.ch.send.assert_called_once_with(newmsg)
            self.assertEqual(self.root.context.get("prop2"),
                             {"subkey": ["one", "two"]})
