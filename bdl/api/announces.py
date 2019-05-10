import logging
from pymacaron_core.swagger.apipool import ApiPool
from bdl.exceptions import IndexNotSupportedError
from bdl.model.announce import model_to_announce


log = logging.getLogger(__name__)


def do_process_announces(data):

    if data.index and data.index != 'BDL':
        raise IndexNotSupportedError(data.index)

    if data.real not in (True, False):
        data.real = True

    if data.source == 'TEST':
        data.real = False

    for a in data.announces:

        # Make sure all required announce attributes are set
        assert a.native_url, "Announce native_url is not set"
        assert a.is_sold in (True, False), "Announce is_complete is not set (%s)" % a.native_url
        if not a.is_sold:
            log.debug("----> is_complete: %s" % a.is_complete)
            assert a.is_complete in (True, False), "Announce is_complete is not set (%s)" % a.native_url
            assert a.title is not None, "Announce title is not set (%s)" % a.native_url
            assert a.price is not None, "Announce price is not set (%s)" % a.native_url
            assert a.currency, "Announce currency is not set (%s)" % a.native_url
        if a.is_complete:
            assert a.description is not None, "Announce description is not set"
            assert a.native_picture_url, "Announce native_picture_url is not set"
            assert a.country, "Announce country is not set"

        model_to_announce(a)
        a.source = data.source
        a.real = data.real

        if a.price_is_fixed not in (True, False):
            a.price_is_fixed = False

        a.process(index=data.index)

    return ApiPool.bdl.model.Ok()


def do_get_announces_to_parse(limit, goal):
    """Return a list of announces that are waiting to be properly parsed so they
    can be curated.
    """
    # TODO: get announces to parse from the queue
    pass
