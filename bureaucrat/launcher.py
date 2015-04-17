import json
import pika
import xml.etree.ElementTree as ET

from configs import Configs
from utils import context2dict

class Launcher(object):
    """Launches workflow processes."""

    def __init__(self, config=None):
        """Initialize launcher."""

        if config is None:
            configs = Configs()
            config  = dict(configs.items("amqp"))

        amqp_host = config.get("host", "localhost")
        amqp_user = config.get("user", "guest")
        amqp_passwd = config.get("passwd", "guest")
        amqp_vhost = config.get("vhost", "/")
        credentials = pika.PlainCredentials(amqp_user, amqp_passwd)
        self.amqp_params = pika.ConnectionParameters(
            credentials=credentials,
            host=amqp_host,
            virtual_host=amqp_vhost)
        self.launcher_key = config.get("launcher_routing_key", "bureaucrat")
        self.exchange = config.get("launcher_exchange", "")

    def launch(self, process_path, fields):
        """Launch process."""

        tree = ET.parse(process_path)
        proc_elem = tree.getroot()
        assert proc_elem.tag == 'process'

        # TODO: better serialization/deserialization code
        context = {}
        ctx = proc_elem.find('context')
        if ctx is not None:
            context = context2dict(ctx)
            proc_elem.remove(ctx)
        context.update(fields)

        ctx = ET.Element('context')
        for key, value in context.items():
            proptype = type(value)
            if proptype is bool:
                prop = ET.Element('property', type='bool', name=key)
                prop.text = str(int(value))
            elif proptype is float:
                prop = ET.Element('property', type='float', name=key)
                prop.text = str(value)
            elif proptype in (str, unicode):
                prop = ET.Element('property', type='str', name=key)
                prop.text = value
            elif proptype is int:
                prop = ET.Element('property', type='int', name=key)
                prop.text = str(value)
            else:
                prop = ET.Element('property', type='json', name=key)
                prop.text = json.dumps(value)
            ctx.append(prop)

        proc_elem.insert(0, ctx)
        pdef = ET.tostring(proc_elem)

        connection = pika.BlockingConnection(self.amqp_params)
        channel = connection.channel()
        channel.basic_publish(exchange=self.exchange,
                              routing_key=self.launcher_key,
                              body=pdef,
                              properties=pika.BasicProperties(
                                  delivery_mode=2
                              ))
        connection.close()
