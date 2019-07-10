import logging
from pymacaron_async import asynctask
from pymacaron_core.swagger.apipool import ApiPool
from pymacaron.config import get_config
from bdl.exceptions import IndexNotSupportedError
from bdl.db.item import get_item
from bdl.model.scrapedobject import model_to_scraped_object
from bdl.db.elasticsearch import es_search_index
from bdl.db.elasticsearch import get_all_docs
from bdl.io.slack import do_slack
from bdl.exceptions import InvalidDataError
from bdl.api.search import doc_to_item


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

        do_slack(
            "Process: doing %s on item %s (%s)" % (action, item_id, o.native_url),
            channel=get_config().slack_api_channel,
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


def do_rescan_items(data):
    """Rescan a percentage of all listed announces from a given source, starting
    with the oldest ones.

    """

    # Validate input data
    if data.index and data.index != 'BDL':
        raise IndexNotSupportedError(data.index)

    if data.percentage < 1 or data.percentage > 100:
        raise InvalidDataError("percentage %s is not between 1 and 100" % data.percentage)

    rescan_items_async(data.source, data.percentage)

    return ApiPool.api.model.Ok()


@asynctask()
def rescan_items_async(source, percentage):

    # How many items do we have listed from this source?
    res = es_search_index(
        index_name='bdlitems-live',
        doc_type='BDL_ITEM',
        sort=[],
        query='SOURCE_%s' % source.upper(),
        page=0,
        item_per_page=1,
    )

    total_hits = res['hits']['total']

    # How many items should we rescan?
    count_rescan = int(total_hits * percentage / 100)

    # Now get count_rescan items from the index, sorting them by last date_last_checked
    batch_size = 100
    esquery = {
        "size": batch_size,
        "sort": [
            {"epoch_last_check": 'asc'}
        ],
        "query": {
            "match": {
                "free_search": {
                    "query": "SOURCE_%s" % source,
                    "operator": "and"
                }
            }
        }
    }

    for doc in get_all_docs(esquery, 'bdlitems-live', 'BDL_ITEM', batch_size=batch_size, limit=count_rescan):
        i = doc_to_item(doc)

        # And schedule a scan of each of those items

        # Note: does not matter if the scrape call fails. It will be retried on
        # the next rescan
        ApiPool.crawler.client.scrape_page(
            ApiPool.crawler.model.ScrapeSettings(
                source=i.source,
                native_url=i.native_url,
            )
        )

    do_slack(
        "Rescan %s oldest items from %s (out of %s)" % (count_rescan, source, total_hits),
        channel=get_config().slack_scheduler_channel,
    )
    pass
