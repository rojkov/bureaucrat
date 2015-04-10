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

    def __repr__(self):
        """Instance representation."""
        return "<%s[%s]>" % (self.__class__.__name__, self)

    @staticmethod
    def load(definition_path, pid):
        """Load a process instance for the given definition."""
        LOG.debug("Load a process definition from %s" % definition_path)

        tree = ET.parse(definition_path)
        root = tree.getroot()
        assert root.tag == 'process'

        process = Process()
        process.uuid = pid

        el_index = 0
        for element in root:
            tag = element.tag
            LOG.debug("Looking into %s" % tag)

            if tag in get_supported_flowexpressions():
                process.children.append(
                    create_fe_from_element(process.uuid, element,
                                           "%s_%d" % (process.uuid, el_index)))
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

        process = Process.load(defpath, newid)
        return process

    def handle_event(self, event):
        """Handle event in process instance."""
        LOG.debug("Handling %r in %r" % (event, self))

        if event.name == 'start' and event.target == self.uuid:
            if len(self.children) > 0:
                event.target = "%s_%d" % (self.uuid, 0)
                event.trigger()
                return False
            else:
                return True

        if event.target == self.uuid and event.name == 'completed':
            for index, child in zip(range(0, len(self.children)), self.children):
                if child.id == event.workitem.origin:
                    if (index + 1) < len(self.children):
                        event.target = "%s_%d" % (self.uuid, (index + 1))
                        event.workitem.event_name = 'start'
                        event.workitem.origin = self.uuid
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

    def resume(self):
        """Resume suspended process."""
        LOG.debug("Resume process %s", self.uuid)
        snapshot = None
        with open(os.path.join(SNAPSHOT_PATH,
                               "process-%s" % self.uuid), 'r') as fhdl:
            snapshot = json.load(fhdl)
        for child, state in zip(self.children, snapshot['children']):
            child.reset_state(state)
