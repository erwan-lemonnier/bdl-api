import logging
from pymacaron_core.swagger.apipool import ApiPool


log = logging.getLogger(__name__)


def do_queue_up_announces(data):

    # Queue up new announces
    # If has too little data on announce:
    #   If announce pass preliminary curation:
    #     Queue up announce for later detailed scrapping
    #   Else:
    #     Drop announce
    #     Remove from SQS if has announce_id
    # Else:
    #   If announce pass deep curation:
    #     Create an item
    #     Remove from SQS if has announce_id
    #   Else:
    #     Drop announce
    #     Remove from SQS if has announce_id

    pass


def do_get_announces_to_parse(limit):
    """Return a list of announces that are waiting to be properly parsed so they
    can be curated.
    """
    pass


def do_get_announces_to_check(limit):
    """Return a list of announces to verify, to see if they are still on sale or not"""
    # List announces from elasticsearch, order by epoch_last_check ascending
    # and return the 'limit' first ones
    # Update epoch_last_check on all the corresponding items and reindex them
    pass
