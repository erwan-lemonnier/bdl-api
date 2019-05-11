import logging


log = logging.getLogger(__name__)


def do_search_items(query, page=0, real=None, country=None, domain=None):
    # TODO: implement search endpoint
    pass

    # real = boolstr_to_bool(real, True)
    # item_per_page = 50

    # if not page:
    #     page = 0

    # if not query:
    #     query = '*'

    # if not domain:
    #     domain = 'kluemarket.com'

    # res = search_item_sold_index(query, page, item_per_page, country, real=real)

    # solditems = []
    # count_found = res['hits']['total']
    # for doc in res['hits']['hits']:
    #     doc_id = doc['_id']
    #     if doc_id.lower() != doc_id:
    #         log.info("#######  DELETING %s" % doc_id)
    #         get_es().delete(
    #             index='items-sold-live',
    #             doc_type='SOLD_ITEM',
    #             id=doc_id,
    #             refresh=True,
    #             ignore=[404],
    #         )
    #         continue

    #     item = doc_to_item_sold(doc, domain)
    #     if is_error(item):
    #         # Skip corrupt data
    #         count_found = count_found - 1
    #     else:
    #         solditems.append(item)

    # # Prepare the SearchResultSold object to send back
    # def gen_url(page):
    #     url = '/v1/search/query?query=%s&page=%s&domain=%s' % (quote_plus(query.encode('utf8')), int(page), domain)
    #     if country:
    #         url = url + '&country=%s' % country
    #     return url

    # if count_found <= (page + 1) * item_per_page:
    #     url_next = None
    # else:
    #     url_next = gen_url(page + 1)

    # log.debug("Found: %s" % solditems)
    # return ApiPool.search.model.SearchResultSold(
    #     count_found=count_found,
    #     query=query,
    #     url_this=gen_url(page),
    #     url_next=url_next,
    #     items=solditems,
    # )
