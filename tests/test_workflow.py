import unittest
import os
import os.path

from mock import Mock
from ConfigParser import ConfigParser

from bureaucrat.workflow import Workflow
from bureaucrat.configs import Configs
from bureaucrat.storage import Storage

processdsc = """<?xml version="1.0"?>
<process name="example1">
    <sequence>
        <action participant="participant1" />
        <action participant="participant2" />
        <switch>
            <case>
                <condition>1 &gt; 2</condition>
                <action participant="participant1"></action>
                <action participant="participant2"></action>
            </case>
            <case>
                <condition>True</condition>
                <action participant="participant1"></action>
                <action participant="participant2"></action>
            </case>
        </switch>
    </sequence>
    <while>
        <condition>workitem.fields["counter"] &lt; 4</condition>
        <action participant="participant1"></action>
        <action participant="participant2"></action>
    </while>
    <all>
        <action participant="participant1"></action>
        <action participant="participant2"></action>
    </all>
    <call process="$some_process" />
</process>
"""

STORAGE_DIR = '/tmp/unittest-processes'

class TestWorkflow(unittest.TestCase):
    """Tests for Workflow."""

    def setUp(self):
        """Set up environment."""

        confparser = ConfigParser()
        confparser.add_section('bureaucrat')
        confparser.set('bureaucrat', 'storage_dir', STORAGE_DIR)
        Configs.instance(confparser)
        self.wflow = Workflow.create_from_string(processdsc, 'fake-id')

    def tearDown(self):
        """Clean up environment."""
        Configs._instance = None
        Storage._instance = None
        os.unlink(os.path.join(STORAGE_DIR, "process/fake-id"))
        os.rmdir(os.path.join(STORAGE_DIR, "process"))
        os.unlink(os.path.join(STORAGE_DIR, "definition/fake-id"))
        os.rmdir(os.path.join(STORAGE_DIR, "definition"))
        os.removedirs(STORAGE_DIR)

    def test_create_from_string(self):
        """Test Workflow.create_from_string()."""

        self.assertTrue(self.wflow.process.state == 'ready')

    def test_load(self):
        """Test Workflow.load()."""

        self.wflow.save()
        wflow = Workflow.load(self.wflow.process.id)
        self.assertTrue(wflow.process.state == 'ready')
