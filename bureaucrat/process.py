import logging
import uuid
import json
import os.path
import os
import xml.etree.ElementTree as ET
from flowexpression import get_supported_flowexpressions
from flowexpression import create_fe_from_element

LOG = logging.getLogger(__name__)

# Path to directory where process snapshots are stored
SNAPSHOT_PATH = '/tmp/processes'

class Process(object):
    """This class represents a workflow process that can be instantiated."""

    def __init__(self):
        """Constructor."""

        self.context = None
        self.uuid = None
        self.children = []
        self.version = 0

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

            if tag in get_supported_flowexpressions():
                process.children.append(
                    create_fe_from_element('', element, "%d" % el_index))
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

        if event.name == 'start' and event.target == '':
            if len(self.children) > 0:
                event.target = '0'
                event.trigger()
                return False
            else:
                return True

        if event.target == '' and event.name == 'completed':
            for index, child in zip(range(0, len(self.children)), self.children):
                if child.id == event.workitem.fei:
                    if (index + 1) < len(self.children):
                        event.target = "%d" % (index + 1)
                        event.workitem.event_name = 'start'
                        event.workitem.fei = ''
                        event.trigger()
                        return False
                    else:
                        return True

        for child in self.children:
            if child.handle_event(event) == 'consumed':
                break

        return False

    def suspend(self):
        """Suspend process instance."""
        LOG.debug("Suspending process %s", self)

        if not os.path.isdir(SNAPSHOT_PATH):
            os.makedirs(SNAPSHOT_PATH)

        snapshot = {
            "version": self.version,
            "children": [child.snapshot() for child in self.children]
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
        for child, state in zip(self.children, snapshot['children']):
            child.reset_state(state)

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
