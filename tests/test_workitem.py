import unittest
import os
import os.path
import json

from ConfigParser import ConfigParser

from bureaucrat.workitem import Workitem
from bureaucrat.configs import Configs
from bureaucrat.workflow import setup_storage

STORAGE_DIR = '/tmp/unittest-processes'

class TestWorkitem(unittest.TestCase):
    """Tests for Workitem."""

    def setUp(self):
        """Set up SUT."""
        setup_storage(STORAGE_DIR)
        confparser = ConfigParser()
        confparser.add_section('bureaucrat')
        confparser.set('bureaucrat', 'storage_dir', STORAGE_DIR)
        Configs.instance(confparser)
        self.subscriptions = [{
                "target": "some-id",
                "context": {"test0": "test0"}
            }]
        with open(os.path.join(STORAGE_DIR,
                               "subscriptions/test_event"), 'w') as fhdl:
            json.dump(self.subscriptions, fhdl)

    def tearDown(self):
        """Clean up environment."""
        Configs._instance = None
        os.unlink(os.path.join(STORAGE_DIR, "subscriptions/test_event"))
        os.rmdir(os.path.join(STORAGE_DIR, "schedule"))
        os.rmdir(os.path.join(STORAGE_DIR, "process"))
        os.rmdir(os.path.join(STORAGE_DIR, "definition"))
        os.rmdir(os.path.join(STORAGE_DIR, "subscriptions"))
        os.removedirs(STORAGE_DIR)

    def test_subscribe(self):
        """Test Workitem.subscribe()."""

        workitem = Workitem({"test": "test"})
        workitem.subscribe(event="test_event", target="fake-id")
        with open(os.path.join(STORAGE_DIR,
                               "subscriptions/test_event")) as fhdl:
            self.subscriptions.append({
                "target": "fake-id",
                "context": {"test": "test"}
            })
            self.assertEqual(fhdl.read(), json.dumps(self.subscriptions))
