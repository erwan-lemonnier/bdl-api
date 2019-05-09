import logging
from pymacaron_core.swagger.apipool import ApiPool
from bdl.exceptions import IndexNotSupportedError
from bdl.model.announce import model_to_announce
from bdl.model.item import create_item
from bdl.db.item import get_item_by_native_url


log = logging.getLogger(__name__)


def do_process_announces(data):

    if data.index and data.index != 'BDL':
        raise IndexNotSupportedError(data.index)

    if data.real not in (True, False):
        data.real = True

    if data.source == 'TEST':
        data.real = False

    for a in data.announces:
        model_to_announce(a)

        assert a.is_complete in (True, False), "Announce is_complete is not set"
        assert a.title is not None, "Announce title is not set"
        assert a.price is not None, "Announce price is not set"
        assert a.currency, "Announce currency is not set"
        assert a.native_url, "Announce native_url is not set"

        if not a.language:
            a.identify_language()

        if not a.is_complete():

            # Is this announce really complete?
            assert a.description is not None, "Announce description is not set"
            assert a.native_picture_url, "Announce native_picture_url is not set"

            if a.pass_curator(ignore_whitelist=True):
                log.info("Announce passes 1st curation: '%'" % str(a))
                a.queue_up()
            else:
                log.info("Announce failed 1st curation: '%'" % str(a))
        else:
            if a.pass_curator():
                log.info("Announce passes deep curation: '%'" % str(a))

                # TODO: check whether an item already exists for this announce
                item = get_item_by_native_url()
                if item:
                    log.info("Announce is already indexed as item '%'" % item.item_id)
                else:
                    log.info("Creating Item for announce '%'" % str(a))
                    create_item(
                        a,
                        index=data.index,
                        real=data.real,
                        source=data.source
                    )
            else:
                log.info("Announce failed deep curation: '%'" % str(a))

    return ApiPool.bdl.model.Ok()


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
