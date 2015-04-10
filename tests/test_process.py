import unittest

from bureaucrat.process import Process

class TestProcess(unittest.TestCase):
    """Tests for Process."""

    def test_constructor(self):
        """Test Process.__init__()."""

        process = Process()

    def test_load(self):
        """Test Process.load()."""

        process = Process.load('examples/processes/example1.xml', 'fake-id')
        self.assertTrue(len(process.children) > 0)
