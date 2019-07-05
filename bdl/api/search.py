import logging
from urllib.parse import quote_plus
from pymacaron_core.swagger.apipool import ApiPool
from bdl.exceptions import InternalServerError
from bdl.exceptions import ESItemNotFoundError
from bdl.model.item import model_to_item
from bdl.db.elasticsearch import es_search_index, es_delete_doc


log = logging.getLogger(__name__)


def doc_to_item(doc):
    item = ApiPool.api.json_to_model('Item', doc['_source'])
    model_to_item(item)
    return item


def do_search_latest_item(source=None):
    """Query the elasticsearch index for the given source and retrieve the newest item or None"""
    assert source

    res = es_search_index(
        index_name='bdlitems-live',
        doc_type='BDL_ITEM',
        sort=[
            {'date_created': {'order': 'desc'}},
        ],
        query='SOURCE_%s' % source.upper(),
        page=0,
        item_per_page=1,
    )

    if 'hits' in res and len(res['hits']['hits']):
        hit = res['hits']['hits'][0]
        return doc_to_item(hit)

    raise ESItemNotFoundError('Found no items from source %s' % source)


def do_search_items(query=None, page=0, page_size=None, real=None, location=None, index=None):

    if real not in (True, False):
        real = True

    if not page_size:
        page_size = 50

    if not index:
        index = 'BDL'
    index = index.upper()

    if not page:
        page = 0

    if not location:
        location = 'ALL'

    location = location.upper()
    assert location in ('ALL', 'SE', 'AROUND_SE')

    internal_query = query if query else ''
    if location != 'ALL':
        internal_query = '%s %s' % (query, location)
    internal_query.strip()

    suffix = 'live' if real else 'test'

    if index == 'BDL':
        index_name = 'bdlitems-' + suffix
    else:
        raise InternalServerError("Don't know how to search index %s" % index)

    res = es_search_index(
        index_name=index_name,
        doc_type='BDL_ITEM',
        sort=[
            {'count_views': {'order': 'desc'}},
            {'display_priority': {'order': 'desc'}},
            {'date_created': {'order': 'desc'}},
        ],
        query=internal_query,
        page=page,
        item_per_page=page_size,
    )

    count_found = res['hits']['total']
    items = []
    for doc in res['hits']['hits']:
        j = doc['_source']

        # NOTE: ugly patch to cleanup early broken data - Remove soon
        if j['date_created'] <= '2019-06-01':
            log.debug("ES document %s is outdated (%s) - Deleting it" % (j['item_id'], j['date_created']))
            es_delete_doc(index_name, 'BDL_ITEM', j['uid'])
            count_found = count_found - 1
            continue

        import json
        log.debug("Looking at item: %s" % json.dumps(j, indent=4))
        items.append(doc_to_item(j))

    # Query urls for the current and next page
    def gen_url(page):
        url = '/v1/search?page=%s&page_size=%s' % (

            int(page),
            int(page_size),
        )
        if query:
            url = url + '&query=%s' % quote_plus(query.encode('utf8'))
        if location:
            url = url + '&location=%s' % location
        if not real:
            url = url + '&real=false'
        return url

    # Result object
    results = ApiPool.api.model.SearchedItems(
        query=query,
        location=location,
        count_found=count_found,
        url_this=gen_url(page),
        items=items,
    )

    if count_found > (page + 1) * page_size:
        results.url_next = gen_url(page + 1)

    return results
