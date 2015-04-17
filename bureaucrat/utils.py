"""Bureaucrat utility functions.

Ideally this module should not exist, but at the moment it contains
the code that would be duplicated otherwise.
"""

import json

def context2dict(element):
    """Convert context from a given element to dictionary.

    :param element: context XML Element
    :type element: xml.etree.ElementTree.Element

    :rtype: dict
    """

    context = {}
    for child in element:
        if child.tag == 'property':
            proptype = child.attrib["type"]
            value = None
            key = child.attrib["name"]
            if proptype == 'int':
                value = int(child.text)
            elif proptype == 'float':
                value = float(child.text)
            elif proptype == 'str':
                value = unicode(child.text)
            elif proptype == 'bool':
                value = bool(int(child.text))
            elif proptype == 'json':
                value = json.loads(child.text)
            else:
                raise TypeError("Unknown property type in the " + \
                                "definition: '%s'" % proptype)
            context[key] = value

    return context
