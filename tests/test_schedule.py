import unittest
import os
import os.path
import json

from ConfigParser import ConfigParser
from mock import patch
from mock import Mock

from bureaucrat.schedule import Schedule
from bureaucrat.configs import Configs

STORAGE_DIR = '/tmp/unittest-processes'

class TestSchedule(unittest.TestCase):
    """Tests for Schedule class."""

    def setUp(self):
        """Set up SUT."""
        confparser = ConfigParser()
        confparser.add_section('bureaucrat')
        confparser.set('bureaucrat', 'storage_dir', STORAGE_DIR)
        Configs.instance(confparser)
        self.ch = Mock()
        self.schedule = Schedule(self.ch)

    def tearDown(self):
        """Clean up environment."""
        Configs._instance = None

    def test_register(self):
        """Test Schedule.register()."""

        instant = 10000
        self.schedule.register(code="timeout", instant=instant,
                               target="fake-id", context={})
        with open(os.path.join(STORAGE_DIR,
                               "schedule/%d" % instant)) as fhdl:
            schedules = [{
                "code": "timeout",
                "target": "fake-id",
                "context": {}
            }]
            self.assertEqual(fhdl.read(), json.dumps(schedules))
        os.unlink(os.path.join(STORAGE_DIR, "schedule/%d" % instant))
        os.rmdir(os.path.join(STORAGE_DIR, "schedule"))
        os.rmdir(os.path.join(STORAGE_DIR, "process"))
        os.rmdir(os.path.join(STORAGE_DIR, "definition"))
        os.removedirs(STORAGE_DIR)

    def test_handle_alarm(self):
        """Test Schedule.handle_alarm()."""

        instant = 10000
        folder = os.path.join(STORAGE_DIR, "schedule")
        with open(os.path.join(folder, "%d" % instant), 'w') as fhdl:
            schedules = [{
                "code": "timeout",
                "target": "fake-id",
                "context": {}
            }]
            json.dump(schedules, fhdl)
        with patch('bureaucrat.schedule.Workitem') as mock_wiclass:
            mock_wi = Mock()
            mock_wiclass.return_value = mock_wi
            self.schedule.handle_alarm()
            mock_wiclass.assert_called_once()
            mock_wi.send.assert_called_once_with(self.ch,
                                                 message='timeout',
                                                 origin='',
                                                 target='fake-id')
