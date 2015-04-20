from __future__ import absolute_import

import logging
import json
import os
import os.path

import xml.etree.ElementTree as ET
from ConfigParser import NoSectionError

from bureaucrat.configs import Configs
from bureaucrat.flowexpression import Process

LOG = logging.getLogger(__name__)

# Path to directory where process snapshots are stored
DEFAULT_PROCESS_DIR = '/tmp/processes'


def setup_storage(storage_dir):
    """Set up storage if it hasn't been set up yet."""

    if not os.path.isdir(storage_dir):
        os.makedirs(os.path.join(storage_dir, "definition"))
        os.makedirs(os.path.join(storage_dir, "process"))
        os.makedirs(os.path.join(storage_dir, "schedule"))


class Workflow(object):
    """Represnts workflow instance."""

    def __init__(self, process):
        """Initialize workflow instance."""

        self.process = process

    @staticmethod
    def create_from_string(pdef, pid):
        """Create Workflow instance from process definition string."""

        LOG.debug("Creating workflow instance from string.")

        # TODO: refactor config storage
        config = Configs()
        try:
            items = dict(config.items("bureaucrat"))
            process_dir = items.get("process_dir", DEFAULT_PROCESS_DIR)
        except NoSectionError:
            process_dir = DEFAULT_PROCESS_DIR

        setup_storage(process_dir)

        defpath = os.path.join(process_dir, "definition/%s" % pid)
        with open(defpath, 'w') as fhdl:
            fhdl.write(pdef)

        xmlelement = ET.fromstring(pdef)
        assert xmlelement.tag == 'process'

        parent_id = ''
        if "parent" in xmlelement.attrib:
            parent_id = xmlelement.attrib["parent"]

        process = Process(parent_id, xmlelement, pid)
        workflow = Workflow(process)
        workflow.save()
        return workflow

    @staticmethod
    def load(process_id):
        """Return existing workflow instance loaded from storage."""

        # TODO: refactor config storage
        config = Configs()
        try:
            items = dict(config.items("bureaucrat"))
            process_dir = items.get("process_dir", DEFAULT_PROCESS_DIR)
        except NoSectionError:
            process_dir = DEFAULT_PROCESS_DIR
        pdef_path = os.path.join(process_dir, "definition/%s" % process_id)
        LOG.debug("Load a process definition from %s", pdef_path)
        tree = ET.parse(pdef_path)
        xmlelement = tree.getroot()
        assert xmlelement.tag == 'process'

        parent_id = ''
        if "parent" in xmlelement.attrib:
            parent_id = xmlelement.attrib["parent"]

        process = Process(parent_id, xmlelement, process_id)
        with open(os.path.join(process_dir,
                               "process/%s" % process.id), 'r') as fhdl:
            snapshot = json.load(fhdl)
            process.reset_state(snapshot)
        return Workflow(process)

    def save(self):
        """Save workflow state to storage."""

        # TODO: refactor config storage
        config = Configs()
        try:
            items = dict(config.items("bureaucrat"))
            process_dir = items.get("process_dir", DEFAULT_PROCESS_DIR)
        except NoSectionError:
            process_dir = DEFAULT_PROCESS_DIR

        setup_storage(process_dir)

        with open(os.path.join(process_dir, "process/%s" % self.process.id),
                  'w') as fhdl:
            json.dump(self.process.snapshot(), fhdl)
