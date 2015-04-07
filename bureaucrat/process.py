import logging
import uuid
import json
import os.path
import os
import xml.etree.ElementTree as ET
from activity import get_supported_activities
from activity import create_activity_from_element

LOG = logging.getLogger(__name__)

# Path to directory where process snapshots are stored
SNAPSHOT_PATH = '/tmp/processes'

#TODO: Process is a Flow Expression too (with children and whose children link to their parent)
class Process(object):
    """This class represents a workflow process that can be instantiated."""

    def __init__(self):
        """Constructor."""

        self.context = None
        self.uuid = None
        self.activities = []
        self.version = 0
        self.state = None
        self.id = ''

    def __str__(self):
        """Return string representation of process."""
        return self.uuid

    @staticmethod
    def load(definition_path):
        """Load a process instance for the given definition."""
        LOG.debug("Load a process definition from %s" % definition_path)

        tree = ET.parse(definition_path)
        root = tree.getroot()
        assert root.tag == 'process'

        process = Process()

        el_index = 0
        for element in root:
            tag = element.tag
            LOG.debug("Looking into %s" % tag)

            if tag in get_supported_activities():
                process.activities.append(
                    create_activity_from_element(process, element,
                                                 "%d" % el_index))
                el_index = el_index + 1
            else:
                LOG.warning("Unknown element: %s", tag)

        return process

    @staticmethod
    def create(definition):
        """Create process instance from string."""
        LOG.debug("Creating process instance from string.")

        newid = "%s" % uuid.uuid4()

        # TODO: drop duplicates, consider decorator
        if not os.path.isdir(SNAPSHOT_PATH):
            os.makedirs(SNAPSHOT_PATH)

        defpath = os.path.join(SNAPSHOT_PATH, "definition-%s" % newid)
        with open(defpath, 'w') as fhdl:
            fhdl.write(definition)

        process = Process.load(defpath)
        process.uuid = newid
        return process

    def handle_event(self, event):
        """Handle event in process instance."""
        LOG.debug("Handling event %s in process %s" % (event, self))

        if event.target == '' and event.name == 'completed':
            LOG.debug("Process %s is completed" % self)
            self.state = 'completed'
            self.suspend()
            return

        for activity in self.activities:
            if activity.handle_event(event) == 'consumed':
                self.suspend()
                break

    def suspend(self):
        """Suspend process instance."""
        LOG.debug("Suspending process %s", self)

        if not os.path.isdir(SNAPSHOT_PATH):
            os.makedirs(SNAPSHOT_PATH)

        snapshot = {
            "version": self.version,
            "activities": [activity.snapshot() for activity in self.activities]
        }

        with open(os.path.join(SNAPSHOT_PATH, "process-%s" % self.uuid),
                  'w') as fhdl:
            json.dump(snapshot, fhdl)

    def resume(self, proc_id):
        """Resume suspended process."""
        LOG.debug("Resume process %s", proc_id)
        self.uuid = proc_id
        snapshot = None
        with open(os.path.join(SNAPSHOT_PATH,
                               "process-%s" % proc_id), 'r') as fhdl:
            snapshot = json.load(fhdl)
        for activity, state in zip(self.activities, snapshot['activities']):
            activity.reset_state(state)

def test():
    process1 = Process.load('examples/processes/example1.xml')
    process1.execute()
    process2 = Process.load('examples/processes/example1.xml')
    process2.resume(process1.uuid)
    event1 = {
        "process_id": process1.uuid,
        "activity_id": "0_0",
        "type": "response"
    }
    process2.handle_event(event1)
    LOG.info("process2 state %s", process2.state)
    event2 = {
        "process_id": process1.uuid,
        "activity_id": "0_1",
        "type": "response"
    }
    process2.handle_event(event2)
    LOG.info("process2 state %s", process2.state)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    test()
