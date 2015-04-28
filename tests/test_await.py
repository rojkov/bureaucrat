import unittest
import os
import os.path
import json
import xml.etree.ElementTree as ET

from ConfigParser import ConfigParser

from mock import Mock
from mock import patch

from bureaucrat.flowexpression import Await
from bureaucrat.context import Context
from bureaucrat.configs import Configs
from bureaucrat.storage import Storage
from bureaucrat.message import Message

processdsc = """<?xml version="1.0"?>
<await event="test_event">
    <condition>True</condition>
</await>
"""

STORAGE_DIR = '/tmp/unittest-processes'

class TestAwait(unittest.TestCase):
    """Tests for Await activity."""

    def setUp(self):
        """Set up SUT."""
        xml_element = ET.fromstring(processdsc)
        self.fexpr = Await('fake-id', xml_element, 'fake-id_0', Context())
        self.ch = Mock()

    # TODO: move these two cases to a base class
    def test_handle_message_completed_state(self):
        """Test Await.handle_message() when Await is completed."""

        msg = Message(name='start', target='fake-id_0', origin='fake-id')
        self.fexpr.state = 'completed'
        result = self.fexpr.handle_message(self.ch, msg)
        self.assertEqual(result, 'ignored')

    def test_handle_message_wrong_target(self):
        """Test Await.handle_message() when message targeted not to it."""

        msg = Message(name='start', target='fake-id_10', origin='fake-id')
        self.fexpr.state = 'active'
        result = self.fexpr.handle_message(self.ch, msg)
        self.assertEqual(result, 'ignored')

    def test_handle_message_start(self):
        """Test Await.handle_message() with 'start' message."""
        confparser = ConfigParser()
        confparser.add_section('bureaucrat')
        confparser.set('bureaucrat', 'storage_dir', STORAGE_DIR)
        Configs.instance(confparser)
        subscriptions = [{
                "target": "some-id"
            }]
        Storage.instance().save("subscriptions", "test_event",
                                json.dumps(subscriptions))

        msg = Message(name='start', target='fake-id_0', origin='fake-id')
        self.fexpr.state = 'ready'
        result = self.fexpr.handle_message(self.ch, msg)
        self.assertEqual(result, 'consumed')
        self.assertEqual(self.fexpr.state, 'active')
        filename = os.path.join(STORAGE_DIR, "subscriptions/test_event")
        with open(filename) as fhdl:
            subscriptions.append({
                'target': 'fake-id_0'
            })
            self.assertEqual(json.load(fhdl), subscriptions)

        Configs._instance = None
        Storage._instance = None
        os.unlink(filename)
        os.rmdir(os.path.join(STORAGE_DIR, "subscriptions"))
        os.removedirs(STORAGE_DIR)

    def test_handle_message_timeout(self):
        """Test Await.handle_message() with 'triggered' message."""

        msg = Message(name='triggered', target='fake-id_0', origin='fake-id_0')
        newmsg = Message(name='completed', target='fake-id', origin='fake-id_0')
        self.fexpr.state = 'active'
        with patch('bureaucrat.flowexpression.Message') as MockMessage:
            MockMessage.return_value = newmsg
            result = self.fexpr.handle_message(self.ch, msg)
            self.assertEqual(result, 'consumed')
            self.assertEqual(self.fexpr.state, 'completed')
            self.ch.send.assert_called_once_with(newmsg)
