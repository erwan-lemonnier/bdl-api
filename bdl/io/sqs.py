import logging
from pymacaron.config import get_config
from boto import sqs
from time import sleep
from boto.sqs.message import Message
import json

log = logging.getLogger(__name__)

conn = None

queues = {}

def get_sqs_conn():
    global conn
    if not conn:
        conf = get_config()
        conn = sqs.connect_to_region(
            conf.aws_region,
            aws_access_key_id=conf.aws_access_key_id,
            aws_secret_access_key=conf.aws_secret_access_key
        )

    return conn

def get_queue(qname):
    """Get or create the common log queue, and return it"""
    if qname not in queues:
        conn = get_sqs_conn()
        queues[qname] = conn.create_queue(qname)

    return queues[qname]

def send_message(qname, j):
    q = get_queue(qname)
    m = Message()
    m.set_body(json.dumps(j))
    q.write(m)

def delete_message(qname, message_id):
    get_sqs_conn().delete_message_from_handle(
        get_queue(qname),
        message_id,
    )

def process_messages(qname, callback, loop=True, timeout=2):
    """Wait and return a log message as a json dict"""
    q = get_queue(qname)
    while True:
        rs = q.get_messages(num_messages=10, wait_time_seconds=timeout)
        log.info("Got %s log messages" % len(rs))

        for m in rs:

            # convert message back to json
            try:
                j = json.loads(m.get_body())
            except Exception as e:
                log.error("Failed to decode SQS body: []\nError was: %s" % (m.get_body(), e))
                continue

            # process it
            log.info("Calling %s on %s" % (callback, m.get_body()))
            callback(j)

            # and delete message...
            q.delete_message(m)

        if not loop:
            log.info("Loop disabled: not waiting for more messages")
            break

        # sleep a bit before retrying
        sleep(5)

def empty_queue(qname):
    """Delete all messages in queue"""
    q = get_queue(qname)
    while True:
        rs = q.get_messages(num_messages=10, wait_time_seconds=1)
        if len(rs) == 0:
            return
        log.info("Got %s log messages" % len(rs))
        for m in rs:
            q.delete_message(m)
