import unittest
import os
import os.path

from ConfigParser import ConfigParser

from bureaucrat.configs import Configs
from bureaucrat.storage import Storage
from bureaucrat.storage import StorageError

STORAGE_DIR = '/tmp/unittest-processes'

def tearDownModule():
    """Clean up module."""
    os.removedirs(STORAGE_DIR)

class TestStorage(unittest.TestCase):
    """Tests for Storage."""

    def setUp(self):
        """Set up SUT."""
        confparser = ConfigParser()
        confparser.add_section('bureaucrat')
        confparser.set('bureaucrat', 'storage_dir', STORAGE_DIR)
        Configs.instance(confparser)
        self.storage = Storage.instance()

    def tearDown(self):
        """Clean up environment."""
        Configs._instance = None

    def test_instance(self):
        """Test Storage.instance()."""
        self.assertEqual(self.storage, Storage.instance())
        self.assertTrue(os.path.isdir(STORAGE_DIR))
        with self.assertRaises(StorageError):
            Storage()

    def test_save(self):
        """Test Storage.save()."""

        doc = "<process></process>"
        self.storage.save("definition", "fake-key", doc)
        file_path = os.path.join(STORAGE_DIR, "definition/fake-key")
        with open(file_path) as fd:
            self.assertEqual(doc, fd.read())
        os.unlink(file_path)
        os.rmdir(os.path.join(STORAGE_DIR, "definition"))

    def test_load(self):
        """Test Storage.load()."""

        doc = "<process></process>"
        os.mkdir(os.path.join(STORAGE_DIR, "definition"))
        file_path = os.path.join(STORAGE_DIR, "definition/fake-key")
        with open(file_path, 'w') as fd:
            fd.write(doc)
        self.assertEqual(doc, self.storage.load("definition", "fake-key"))
        os.unlink(file_path)
        os.rmdir(os.path.join(STORAGE_DIR, "definition"))

    def test_delete(self):
        """Test Storage.delete()."""
        doc = "<process></process>"
        os.mkdir(os.path.join(STORAGE_DIR, "definition"))
        file_path = os.path.join(STORAGE_DIR, "definition/fake-key")
        with open(file_path, 'w') as fd:
            fd.write(doc)
        self.storage.delete("definition", "fake-key")
        self.assertFalse(os.path.exists(file_path))
        os.rmdir(os.path.join(STORAGE_DIR, "definition"))

    def test_keys(self):
        """Test Storage.keys()."""

        doc = "<process></process>"
        os.mkdir(os.path.join(STORAGE_DIR, "definition"))
        file_path = os.path.join(STORAGE_DIR, "definition/fake-key")
        with open(file_path, 'w') as fd:
            fd.write(doc)
        self.assertEqual(['fake-key'], self.storage.keys("definition"))
        os.unlink(file_path)
        os.rmdir(os.path.join(STORAGE_DIR, "definition"))
        self.assertEqual(self.storage.keys("definition"), [])
