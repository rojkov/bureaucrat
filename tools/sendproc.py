#!/usr/bin/python

import logging
import pika
import sys
import os.path

from optparse import OptionParser

LOG = logging.getLogger(__name__)

def parse_cmdline():
    """Parse command line options."""

    parser = OptionParser()
    parser.add_option("-p", "--path", dest="path",
                      help="path to process definition")

    (options, args) = parser.parse_args()

    if options.path is None:
        LOG.error("Mandatory option 'path' is missing")
        sys.exit(1)

    return options

def main():
    """Entry point."""

    options = parse_cmdline()
    if not os.path.isfile(options.path):
        LOG.error("File '%s' not found. Exiting..." % options.path)
        sys.exit(1)

    process = ""
    with open(options.path, 'r') as fhdl:
        process = fhdl.read()

    if not len(process):
        LOG.error("Empty process definition.")
        sys.exit(1)

    parameters = pika.ConnectionParameters(host="localhost")

    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    channel.basic_publish(exchange='',
                          routing_key='bureaucrat',
                          body=process,
                          properties=pika.BasicProperties(
                              delivery_mode=2
                          ))
    connection.close()

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
