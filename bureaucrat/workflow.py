from __future__ import absolute_import

import logging
import json

import xml.etree.ElementTree as ET

from bureaucrat.storage import Storage
from bureaucrat.storage import lock_storage
from bureaucrat.flowexpression import Process

LOG = logging.getLogger(__name__)


class Workflow(object):
    """Represnts workflow instance."""

    def __init__(self, process):
        """Initialize workflow instance."""

        self.process = process

    @staticmethod
    def create_from_string(pdef, pid):
        """Create Workflow instance from process definition string."""

        LOG.debug("Creating workflow instance from string.")

        xmlelement = ET.fromstring(pdef)
        assert xmlelement.tag == 'process'

        Storage.instance().save("definition", pid, pdef)

        parent_id = ''
        if "parent" in xmlelement.attrib:
            parent_id = xmlelement.attrib["parent"]

        process = Process(parent_id, xmlelement, pid)
        workflow = Workflow(process)
        workflow.save()
        return workflow

    @staticmethod
    @lock_storage
    def load(process_id):
        """Return existing workflow instance loaded from storage."""

        LOG.debug("Load a process definition from %s", process_id)
        storage = Storage.instance()
        pdef = storage.load("definition", process_id)
        xmlelement = ET.fromstring(pdef)
        assert xmlelement.tag == 'process'

        parent_id = ''
        if "parent" in xmlelement.attrib:
            parent_id = xmlelement.attrib["parent"]

        process = Process(parent_id, xmlelement, process_id)
        process.reset_state(json.loads(storage.load("process", process.id)))
        return Workflow(process)

    @lock_storage
    def save(self):
        """Save workflow state to storage."""

        Storage.instance().save("process", self.process.id,
                                json.dumps(self.process.snapshot()))

    @lock_storage
    def delete(self):
        """Delete workflow instance from storage."""

        storage = Storage.instance()
        storage.delete("process", self.process.id)
        storage.delete("definition", self.process.id)
