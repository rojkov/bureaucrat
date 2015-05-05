from __future__ import absolute_import

import unittest

from mock import Mock
from mock import patch

from bureaucrat.bureaucrat import Bureaucrat

class TestBureaucrat(unittest.TestCase):
    """Tests for Bureaucrat app class."""

    def test_handle_message_wrong_mesage1(self):
        """Test Bureaucrat.handle_message() with wrong formatted message 1."""

        bc = Bureaucrat()
        channel = Mock()

        with patch("bureaucrat.bureaucrat.LOG") as LOG:
            body = """Wrong message"""
            bc.handle_message(channel, Mock(), Mock(), body)
            LOG.error.assert_called_once()

        channel.basic_ack.assert_called_once()

    def test_handle_message_wrong_mesage2(self):
        """Test Bureaucrat.handle_message() with wrong formatted message 2."""

        bc = Bureaucrat()
        channel = Mock()

        with patch("bureaucrat.bureaucrat.LOG") as LOG:
            body = """{}"""
            bc.handle_message(channel, Mock(), Mock(), body)
            LOG.error.assert_called_once()

        channel.basic_ack.assert_called_once()

    def test_handle_message_completed(self):
        """Test Bureaucrat.handle_message() with completed."""

        bc = Bureaucrat()
        channel = Mock()

        with patch("bureaucrat.bureaucrat.Workflow") as MockWfl:
            wflow = Mock()
            MockWfl.load.return_value = wflow
            body = """
                {
                    "name": "completed",
                    "target": "fake-child",
                    "origin": "fake-origin",
                    "payload": null
                }
            """
            bc.handle_message(channel, Mock(), Mock(), body)
            MockWfl.load.assert_called_once()
            wflow.process.handle_message.assert_called_once()
            wflow.save.assert_called_once()

        channel.basic_ack.assert_called_once()

    def test_handle_message_fault(self):
        """Test Bureaucrat.handle_message() with fault."""

        bc = Bureaucrat()
        channel = Mock()

        with patch("bureaucrat.bureaucrat.Workflow") as MockWfl:
            wflow = Mock()
            MockWfl.load.return_value = wflow
            body = """
                {
                    "name": "fault",
                    "target": "fake-child",
                    "origin": "fake-origin",
                    "payload": null
                }
            """
            bc.handle_message(channel, Mock(), Mock(), body)
            MockWfl.load.assert_called_once()
            wflow.process.handle_message.assert_called_once()
            wflow.save.assert_called_once()

        channel.basic_ack.assert_called_once()
