import unittest
import os
import os.path
import json

from ConfigParser import ConfigParser

from bureaucrat.workitem import Workitem
from bureaucrat.configs import Configs
from bureaucrat.storage import Storage

STORAGE_DIR = '/tmp/unittest-processes'

class TestWorkitem(unittest.TestCase):
    """Tests for Workitem."""

    def setUp(self):
        """Set up SUT."""
        confparser = ConfigParser()
        confparser.add_section('bureaucrat')
        confparser.set('bureaucrat', 'storage_dir', STORAGE_DIR)
        Configs.instance(confparser)
        self.subscriptions = [{
                "target": "some-id",
                "context": {"test0": "test0"}
            }]
        Storage.instance().save("subscriptions", "test_event",
                                json.dumps(self.subscriptions))

    def tearDown(self):
        """Clean up environment."""
        Configs._instance = None
        os.unlink(os.path.join(STORAGE_DIR, "subscriptions/test_event"))
        os.rmdir(os.path.join(STORAGE_DIR, "subscriptions"))
        os.removedirs(STORAGE_DIR)

