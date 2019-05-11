import logging
from pymacaron_core.swagger.apipool import ApiPool
from pymacaron.utils import timenow
from bdl.exceptions import IndexNotSupportedError
from bdl.db.item import get_item
from bdl.model.scrapedobject import model_to_scraped_object


log = logging.getLogger(__name__)


def do_process_items(data):
    """Take a list of scraped objects and decide whether to index them or not, or
    queue up tasks to re-scrape them more thoroughly, or update pre-existing
    items, or archive items.

    """

    if data.index and data.index != 'BDL':
        raise IndexNotSupportedError(data.index)

    if data.real not in (True, False):
        data.real = True

    if data.source == 'TEST':
        data.real = False

    for o in data.objects:

        model_to_scraped_object(o)
        o.validate_for_processing()

        o.process(index=dato.index)

    return ApiPool.bdl.model.Ok()


def do_get_item(item_id):
    """Get one item given its ID, from the active index or the archive"""

    item = get_item(item_id)
    item.count_views = item.count_views + 1
    item.save_to_db(async=True)

    return item


def do_archive_item(data, item_id=None):
    """Archive an item"""

    assert data.reason == 'SOLD', "Archiving reason is %s" % data.reason

    item = get_item(item_id)
    subitem = item._get_subitem()

    assert item.index == 'BDL'
    subitem.mark_as_sold(
        price_sold=data.price_sold,
    )

    item.archive()

    return item


def do_get_scraper_tasks(limit, goal):
    """Return a list of scraper tasks"""
    # TODO: get scraper tasks
    pass
