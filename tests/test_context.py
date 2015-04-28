from __future__ import absolute_import
import unittest
import xml.etree.ElementTree as ET

from bureaucrat.context import Context
from bureaucrat.context import ContextError
from bureaucrat.flowexpression import Process

procdsc = """
<process>
    <context>
        <property name="prop1" type="str">test prop 1</property>
    </context>
    <sequence>
        <context>
            <property name="prop2" type="int">5</property>
        </context>
        <while>
            <condition>True</condition>
            <action participant="test" />
            <context>
                <property name="prop2" type="bool">0</property>
                <property name="prop3" type="float">0.5</property>
                <property name="prop4" type="json">{"test": "test"}</property>
            </context>
            <all>
                <context>
                    <property name="prop4" type="json">{"test": "test2"}</property>
                </context>
                <action participant="test" />
            </all>
        </while>
        <action participant="test" />
    </sequence>
</process>
"""

class TestContext(unittest.TestCase):
    """Tests for Context."""

    def setUp(self):
        """Set up SUT."""
        xml_element = ET.fromstring(procdsc)
        self.procexpr = Process('', xml_element, 'fake-id', Context())
        self.seqexpr = self.procexpr.children[0]
        self.whileexpr = self.seqexpr.children[0]
        self.allexpr = self.whileexpr.children[1]

    def test_get(self):
        """Test Context.get()."""

        self.assertEqual(self.whileexpr.context.get('prop4'), {"test": "test"})
        self.assertEqual(self.allexpr.context.get('prop4'), {"test": "test2"})
        self.assertEqual(self.allexpr.context.get('prop3'), 0.5)
        self.assertEqual(self.procexpr.context.get('prop1'), "test prop 1")
        self.assertEqual(self.allexpr.context.get('prop1'), "test prop 1")
        with self.assertRaises(ContextError):
            self.assertEqual(self.procexpr.context.get('prop4'))

    def test_set(self):
        """Test Context.set()."""

        self.allexpr.context.set('prop4', 5)
        self.assertEqual(self.allexpr.context.get('prop4'), 5)
        self.assertEqual(self.whileexpr.context.get('prop4'), {"test": "test"})
        self.allexpr.context.set('prop1', 5)
        self.assertEqual(self.allexpr.context.get('prop1'), 5)
        self.assertEqual(self.whileexpr.context.get('prop1'), 5)
        self.assertEqual(self.seqexpr.context.get('prop1'), 5)
        self.assertEqual(self.procexpr.context.get('prop1'), 5)
        with self.assertRaises(ContextError):
            self.allexpr.context.get('fakeprop')

    def test_update(self):
        """Test Context.update()."""
        self.allexpr.context.update({
            "prop1": 5,
            "newprop": 6,
            "prop4": 7
        })
        self.assertEqual(self.allexpr.context.get('prop1'), 5)
        self.assertEqual(self.allexpr.context.get('newprop'), 6)
        self.assertEqual(self.allexpr.context.get('prop4'), 7)
        self.assertEqual(self.whileexpr.context.get('prop4'), {"test": "test"})
        self.assertEqual(self.procexpr.context.get('prop1'), 5)
        with self.assertRaises(ContextError):
            self.assertEqual(self.procexpr.context.get('newprop'))
