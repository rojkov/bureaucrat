from __future__ import absolute_import

import unittest
import xml.etree.ElementTree as ET

from mock import Mock
from mock import patch

from bureaucrat.flowexpression import Process
from bureaucrat.context import Context
from bureaucrat.context import ContextError
from bureaucrat.message import Message

procdsc = """
<process>
    <sequence>
        <action participant="test" />
        <action participant="test" />
        <context>
            <faults>
                <case code="UnknownError">
                    <action participant="test1" />
                    <action participant="test1" />
                </case>
                <default>
                    <action participant="test3" />
                </default>
                <case code="GenericError, TestError">
                    <action participant="test2" />
                    <action participant="test2" />
                </case>
            </faults>
        </context>
    </sequence>
</process>
"""

class TestFaults(unittest.TestCase):
    """Tests for faults."""

    def setUp(self):
        """Set up test case."""

        xmlelement = ET.fromstring(procdsc)
        self.root = Process('', xmlelement, 'fake-id', Context())
        self.seq = self.root.children[0]
        self.faults = self.seq.faults
        self.ch = Mock()

    def test_starting_faults_handler(self):
        """Test complex activity start fault handler upon receiving a fault."""

        msg = Message(name='canceled', target='fake-id_0', origin='fake-id_0_1')
        self.seq.state = 'aborting'
        self.seq.children[0].state = 'aborted'
        self.seq.children[1].state = 'canceled'
        with patch('bureaucrat.flowexpression.Message') as MockMsg:
            # last handler should be triggered for 'TestError'
            self.seq.context.throw(code='TestError',
                                   message='Some error message')
            newmsg = Message(name='start', target='fake-id_0_faults',
                             origin='fake-id_0')
            MockMsg.return_value = newmsg
            result = self.seq.handle_message(self.ch, msg)
            self.assertEqual(result, 'consumed')
            MockMsg.assert_called_once_with(name='start',
                                            target='fake-id_0_faults',
                                            origin='fake-id_0')
            self.ch.send.assert_called_once_with(newmsg)
            self.assertEqual(self.seq.state, 'aborting')

    def test_starting_particular_handler(self):
        """Test correct fault handler is triggered."""

        msg = Message(name='start', target='fake-id_0_faults',
                      origin='fake-id_0')
        self.seq.state = 'aborting'
        self.seq.children[0].state = 'aborted'
        self.seq.children[1].state = 'canceled'
        with patch('bureaucrat.flowexpression.Message') as MockMsg:
            # last handler should be triggered for 'TestError'
            self.seq.context.throw(code='TestError',
                                   message='Some error message')
            newmsg = Message(name='start', target='fake-id_0_faults_2',
                             origin='fake-id_0_faults')
            MockMsg.return_value = newmsg
            result = self.seq.handle_message(self.ch, msg)
            self.assertEqual(result, 'consumed')
            MockMsg.assert_called_once_with(name='start',
                                            target='fake-id_0_faults_2',
                                            origin='fake-id_0_faults')
            self.ch.send.assert_called_once_with(newmsg)
            self.assertEqual(self.seq.state, 'aborting')
            self.assertEqual(self.seq.faults.state, 'active')

    def test_starting_deafult_handler(self):
        """Test default fault handler is triggered."""

        msg = Message(name='start', target='fake-id_0_faults',
                      origin='fake-id_0')
        self.seq.state = 'aborting'
        self.seq.children[0].state = 'aborted'
        self.seq.children[1].state = 'canceled'
        with patch('bureaucrat.flowexpression.Message') as MockMsg:
            # default handler should be triggered for 'FakeError'
            self.seq.context.throw(code='FakeError',
                                   message='Some error message')
            newmsg = Message(name='start', target='fake-id_0_faults_1',
                             origin='fake-id_0_faults')
            MockMsg.return_value = newmsg
            result = self.seq.handle_message(self.ch, msg)
            self.assertEqual(result, 'consumed')
            MockMsg.assert_called_once_with(name='start',
                                            target='fake-id_0_faults_1',
                                            origin='fake-id_0_faults')
            self.ch.send.assert_called_once_with(newmsg)
            self.assertEqual(self.seq.state, 'aborting')
            self.assertEqual(self.seq.faults.state, 'active')

    def test_handling_message_for_faulthandler_by_faulthandler(self):
        """Test that message for a handler is handled by the handler."""

        self.seq.state = 'aborting'
        self.seq.faults.state = 'active'
        self.seq.context.throw(code='TestError', message='Some error message')
        with patch('bureaucrat.flowexpression.Message') as MockMsg:
            msg = Message(name='start', target='fake-id_0_faults_2',
                          origin='fake-id_0_faults')
            result = self.seq.handle_message(self.ch, msg)
            self.assertEqual(result, 'consumed')
            MockMsg.assert_called_once_with(name='start',
                                            target='fake-id_0_faults_2_0',
                                            origin='fake-id_0_faults_2')
            self.assertEqual(self.seq.state, 'aborting')

        msg = Message(name='start', target='fake-id_0_faults_2_0',
                      origin='fake-id_0_faults_2')
        result = self.seq.handle_message(self.ch, msg)
        self.assertEqual(result, 'consumed')
        self.ch.elaborate.assert_called_once_with("test2",
                                                  "fake-id_0_faults_2_0",
                                                  {
                                                      'status': 'done',
                                                      'inst:fault': {
                                                          'message': 'Some error message',
                                                          'code': 'TestError'
                                                      }
                                                  })
        self.assertEqual(self.seq.state, 'aborting')

    def test_throwing_faults_in_case_hadler_faults_too(self):
        """Faulting handler should cause parent activity to throw fault.

        Also the parent activity should transition to 'aborted' state.
        """

        self.seq.state = 'aborting'
        self.seq.context.throw(code='TestError', message='Some error message')
        msg = Message(name="fault", target="fake-id_0_faults_2",
                      origin="fake-id_0_faults_2_1",
                      payload={"code": "SecondError", "message": ""})
        self.faults.state = 'active'
        self.faults.children[2].state  = 'active'
        self.faults.children[2].children[0].state = 'completed'
        self.faults.children[2].children[1].state = 'aborted'
        with patch('bureaucrat.flowexpression.Message') as MockMsg:
            result = self.seq.handle_message(self.ch, msg)
            self.assertEqual(result, 'consumed')
            MockMsg.assert_called_once_with(name='fault',
                                            target='fake-id_0_faults',
                                            origin='fake-id_0_faults_2',
                                            payload={
                                                "code": "SecondError",
                                                "message": ""
                                            })
            self.assertEqual(self.seq.state, 'aborting')
            self.assertEqual(self.faults.children[2].state, 'aborted')


        msg = Message(name="fault", target="fake-id_0_faults",
                      origin="fake-id_0_faults_2",
                      payload={"code": "SecondError", "message": ""})
        with patch('bureaucrat.flowexpression.Message') as MockMsg:
            result = self.seq.handle_message(self.ch, msg)
            self.assertEqual(result, 'consumed')
            MockMsg.assert_called_once_with(name='fault',
                                            target='fake-id_0',
                                            origin='fake-id_0_faults',
                                            payload={
                                                "code": "SecondError",
                                                "message": ""
                                            })
            self.assertEqual(self.seq.faults.state, 'aborted')

        msg = Message(name="fault", target="fake-id_0",
                      origin="fake-id_0_faults",
                      payload={"code": "SecondError", "message": ""})
        with patch('bureaucrat.flowexpression.Message') as MockMsg:
            result = self.seq.handle_message(self.ch, msg)
            self.assertEqual(result, 'consumed')
            MockMsg.assert_called_once_with(name='fault',
                                            target='fake-id',
                                            origin='fake-id_0',
                                            payload={
                                                "code": "SecondError",
                                                "message": ""
                                            })
            self.assertEqual(self.seq.state, 'aborted')
            self.assertEqual(self.seq.context.get('inst:fault'),
                             {
                                 "code": "SecondError",
                                 "message": ""
                             })

    def test_aborting_handlers_children_if_it_faults(self):
        """Faulting handler aborts all its children before fault propagating.
        """

        self.seq.state = 'aborting'
        self.seq.context.throw(code='TestError', message='Some error message')
        msg = Message(name="fault", target="fake-id_0_faults_2",
                      origin="fake-id_0_faults_2_0",
                      payload={"code": "SecondError", "message": ""})
        self.faults.children[2].state  = 'active'
        self.faults.children[2].children[0].state = 'aborted'
        self.faults.children[2].children[1].state = 'ready'
        with patch('bureaucrat.flowexpression.Message') as MockMsg:
            result = self.seq.handle_message(self.ch, msg)
            self.assertEqual(result, 'consumed')
            MockMsg.assert_called_once_with(name='terminate',
                                            target='fake-id_0_faults_2_1',
                                            origin='fake-id_0_faults_2')
            self.assertEqual(self.seq.state, 'aborting')
            self.assertEqual(self.faults.children[2].state, 'aborting')

    def test_aborting_flowexpression_recovered_by_faults_handler(self):
        """Test aborting flow expression is recovered by fault handler.

        The recovered expression should transition to 'completed' state.
        """

        self.seq.state = 'aborting'
        self.seq.context.throw(code='TestError', message='Some error message')
        msg = Message(name="completed", target="fake-id_0",
                      origin="fake-id_0_faults")
        with patch('bureaucrat.flowexpression.Message') as MockMsg:
            result = self.seq.handle_message(self.ch, msg)
            self.assertEqual(result, 'consumed')
            MockMsg.assert_called_once_with(name='completed', target='fake-id',
                                            origin='fake-id_0')
            self.assertEqual(self.seq.state, 'completed')
            with self.assertRaises(ContextError):
                self.seq.context.get('inst:fault')

    def test_fault_handler_is_completed(self):
        """Test fault handler sends completed if its last child is completed.
        """

        self.seq.state = 'aborting'
        self.seq.context.throw(code='TestError', message='Some error message')
        msg = Message(name="completed", target="fake-id_0_faults_2",
                      origin="fake-id_0_faults_2_1")
        self.faults.children[2].state  = 'active'
        self.faults.children[2].children[0].state = 'completed'
        self.faults.children[2].children[1].state = 'completed'
        with patch('bureaucrat.flowexpression.Message') as MockMsg:
            result = self.seq.handle_message(self.ch, msg)
            self.assertEqual(result, 'consumed')
            MockMsg.assert_called_once_with(name='completed',
                                            target='fake-id_0_faults',
                                            origin='fake-id_0_faults_2')
            self.assertEqual(self.faults.children[2].state, 'completed')
