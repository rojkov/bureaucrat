import unittest
import os
import os.path
import json

from ConfigParser import ConfigParser
from mock import patch
from mock import Mock

from bureaucrat.schedule import Schedule
from bureaucrat.configs import Configs
from bureaucrat.storage import Storage
from bureaucrat.message import Message

STORAGE_DIR = '/tmp/unittest-processes'

class TestSchedule(unittest.TestCase):
    """Tests for Schedule class."""

    def setUp(self):
        """Set up SUT."""
        confparser = ConfigParser()
        confparser.add_section('bureaucrat')
        confparser.set('bureaucrat', 'storage_dir', STORAGE_DIR)
        Configs.instance(confparser)
        Storage.instance()
        self.ch = Mock()
        self.schedule = Schedule(self.ch)

    def tearDown(self):
        """Clean up environment."""
        Configs._instance = None
        Storage._instance = None
        os.rmdir(os.path.join(STORAGE_DIR, "schedule"))
        os.removedirs(STORAGE_DIR)

    def test_register(self):
        """Test Schedule.register()."""

        instant = 10000
        self.schedule.register(code="timeout", instant=instant,
                               target="fake-id")
        storage = Storage.instance()
        schedules = [{
            "code": "timeout",
            "target": "fake-id"
        }]
        self.assertEqual(storage.load("schedule", str(instant)),
                         json.dumps(schedules))
        storage.delete("schedule", str(instant))

    def test_handle_alarm(self):
        """Test Schedule.handle_alarm()."""

        instant = 10000
        storage = Storage.instance()
        schedules = [{
            "code": "timeout",
            "target": "fake-id"
        }]
        storage.save("schedule", str(instant), json.dumps(schedules))
        with patch('bureaucrat.schedule.Message') as MockMessage:
            newmsg = Message(name='timeout', target='fake-id', origin='')
            MockMessage.return_value = newmsg
            self.schedule.handle_alarm()
            self.schedule.channel.send.assert_called_once_with(newmsg)
            self.assertFalse(storage.exists("schedule", str(instant)))
