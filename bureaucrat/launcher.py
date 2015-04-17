import json
import pika
import xml.etree.ElementTree as ET

from configs import Configs

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

        fields_elem = ET.Element('fields')
        fields_elem.text = json.dumps(fields)
        proc_elem.append(fields_elem)
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
