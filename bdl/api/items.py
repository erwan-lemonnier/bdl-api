import logging
from pymacaron_async import asynctask
from pymacaron_core.swagger.apipool import ApiPool
from bdl.exceptions import IndexNotSupportedError
from bdl.db.item import get_item
from bdl.model.scrapedobject import model_to_scraped_object


log = logging.getLogger(__name__)


def do_process_items(data):
    """Take a list of scraped objects and decide whether to index them or not, or
    queue up tasks to re-scrape them more thoroughly, or update pre-existing
    items, or archive items.

    """

    # Validate input data
    if data.index and data.index != 'BDL':
        raise IndexNotSupportedError(data.index)

    if data.real not in (True, False):
        data.real = True

    if data.source == 'TEST':
        data.real = False

    for o in data.objects:

        log.info('Looking at scraped object %s' % str(o.native_url))
        model_to_scraped_object(o)
        o.validate_for_processing()

    # Process objects, asynchronously or not
    synchronous = True if data.synchronous is True else False

    jsons = [ApiPool.api.model_to_json(o) for o in data.objects]

    if synchronous:
        return process_items(data.index, data.source, data.real, *jsons)
    else:
        async_process_items(data.index, data.source, data.real, *jsons)
        return ApiPool.api.model.ProcessResults(results=[])


@asynctask()
def async_process_items(index, source, real, *jsons):
    process_items(index, source, real, *jsons)


def process_items(index, source, real, *jsons):

    results = ApiPool.api.model.ProcessResults(results=[])
    for j in jsons:

        o = ApiPool.api.json_to_model('ScrapedObject', j)
        model_to_scraped_object(o)

        log.info('Looking at scraped object %s' % str(o.native_url))

        action, item_id = o.process(
            index=index,
            source=source,
            real=real,
        )

        results.results.append(
            ApiPool.api.model.ProcessResult(
                action=action,
                item_id=item_id,
            )
        )

    return results


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

    assert item.index == 'BDL'
    item.get_subitem().mark_as_ended(
        subitem=ApiPool.api.model.ScrapedBDLItem(
            has_ended=True,
            date_ended=data.date_ended,
            is_sold=data.is_sold,
            price_sold=data.price_sold,
            date_sold=data.date_sold,
        )
    )
    item.archive()

    return item


def do_get_scraper_tasks(limit, goal):
    """Return a list of scraper tasks"""
    # TODO: get scraper tasks
    pass
