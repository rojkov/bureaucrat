import unittest

from mock import Mock

from bureaucrat.flowexpression import FlowExpression
from bureaucrat.flowexpression import FlowExpressionError

def fake_et_iterator(parent):
    """Fake iterator over child elements."""

    def internal_fake_iterator(parent):
        while False:
            yield None

    xml_element1 = Mock()
    xml_element1.tag = 'sequence'
    xml_element1.__iter__ = internal_fake_iterator
    elements = [xml_element1]

    for elem in elements:
        yield elem

class TestFlowExpression(unittest.TestCase):
    """Tests for FlowExpression."""

    def setUp(self):
        """Set up test case."""
        self.xml_element = Mock()
        self.xml_element.tag = 'flowexpression'

    def test_constructor_no_children(self):
        """Test FlowExpression.__init__() for simple expression."""

        fexpr = FlowExpression('fake-id', self.xml_element, 'fake-id_0')
        self.assertTrue(fexpr.id == 'fake-id_0')

    def test_constructor(self):
        """Test FlowExpression.__init__() for complex expression."""

        self.xml_element.__iter__ = fake_et_iterator
        self.xml_element.tag = 'testexpression'

        class TestExpression(FlowExpression):
            allowed_child_types = ('sequence',)

        fexpr = TestExpression('fake-id', self.xml_element, 'fake-id_0')
        self.assertTrue(fexpr.id == 'fake-id_0')
        self.assertTrue(len(fexpr.children) == 1)
