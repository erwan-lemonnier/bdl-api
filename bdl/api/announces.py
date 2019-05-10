import logging
from pymacaron_core.swagger.apipool import ApiPool
from pymacaron.utils import timenow
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

        # Make sure all required announce attributes are set
        assert a.native_url, "Announce native_url is not set"
        assert a.is_sold in (True, False), "Announce is_complete is not set (%s)" % a.native_url
        assert a.is_complete in (True, False), "Announce is_complete is not set (%s)" % a.native_url
        if not a.is_sold:
            assert a.title is not None, "Announce title is not set (%s)" % a.native_url
            assert a.price is not None, "Announce price is not set (%s)" % a.native_url
            assert a.currency, "Announce currency is not set (%s)" % a.native_url

        # If the announce is sold, we need to archive it
        if a.is_sold:
            log.info("Announce is sold [%s]" % str(a))
            item = get_item_by_native_url(a.native_url)
            if not item:
                log.info("There is NO item based on this announce - Ignoring it")
            else:
                log.info("Found item %s based on this announce - Archiving it" % item.item_id)
                item.is_sold = True
                item.date_sold = timenow()
                if a.price_sold:
                    log.info("Setting item's price_sold: %s" % a.price_sold)
                    item.price_sold = a.price_sold
                item.archive()

        else:
            # This announce is still for sale. Does it pass curation?

            # If no language is specified, use amazon comprehend to identify the
            # announce's language
            if not a.language:
                a.identify_language()
                log.info("Identified announce's language: %s [%s]" % (a.language, str(a)))

            if not a.is_complete():

                # Incomplete announce. Let's decide if we queue it up for complete scraping,
                # or if we drop it already

                if not a.pass_curator(ignore_whitelist=True):
                    log.info("Announce failed 1st curation - Skipping it [%]" % str(a))
                else:
                    log.info("Announce passed 1st curation - Queuing it up [%]" % str(a))
                    a.queue_up()

            else:
                # Is this announce really complete?
                assert a.description is not None, "Announce description is not set"
                assert a.native_picture_url, "Announce native_picture_url is not set"

                if not a.pass_curator():
                    log.info("Announce failed deep curation - Skipping it [%s]" % str(a))
                else:
                    log.info("Announce passed deep curation [%]" % str(a))

                    # TODO: check whether an item already exists for this announce
                    item = get_item_by_native_url()
                    if item:
                        log.info("Announce is already indexed as item %s [%s]" % (item.item_id, str(a)))
                    else:
                        log.info("Creating new Item for announce [%]" % str(a))
                        item = create_item(
                            a,
                            index=data.index,
                            real=data.real,
                            source=data.source
                        )
                        log.info("Item has item_id %s" % item.item_id)

    return ApiPool.bdl.model.Ok()


def do_get_announces_to_parse(limit):
    """Return a list of announces that are waiting to be properly parsed so they
    can be curated.
    """
    # TODO: get announces to parse from the queue
    pass


def do_get_announces_to_check(limit):
    """Return a list of announces to verify, to see if they are still on sale or not"""
    # List announces from elasticsearch, order by epoch_last_check ascending
    # and return the 'limit' first ones
    # Update epoch_last_check on all the corresponding items and reindex them
    pass
