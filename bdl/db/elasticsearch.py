import logging
import re
from elasticsearch import exceptions
from pymacaron.crash import report_error
from pymacaron_async import asynctask
from bdl.exceptions import ESItemNotFoundError, InternalServerError
from bdl.io.es import get_es


log = logging.getLogger(__name__)


def cleanup_string(s):
    s = s.lower()
    s = re.sub('<[^<]+?>', ' ', s)
    # s = html_to_unicode(s)
    s = re.sub(r'[;,*_=+\!\'\"\#\?\´\´\\\/\^\(\)\&\@\|\[\]\{\}\%]', ' ', s)
    s = s.replace('\n', ' ').replace('\r', '')
    s = re.sub(r'\s+', ' ', s)
    s = s.strip()
    return s

#
# Index document
#


@asynctask()
def es_index_doc_async(index_name, doc, doc_type, uid):
    es_index_doc(index_name, doc, doc_type, uid)

def es_index_doc(index_name, doc, doc_type, uid):
    """Insert the document in the given elasticsearch index"""

    assert index_name
    assert doc
    assert uid

    es = get_es()

    doc['uid'] = uid

    # Using 'index' instead of 'create' to purposefully overwrite pre-existing
    # versions of this item. Two different items with same id are deemed
    # similar enough to be considered equal.
    try:
        r = es.index(
            index=index_name,
            doc_type=doc_type,
            id=uid,
            body=doc,
            refresh=True,
        )
        log.info("ES.index() returns %s" % r)

        if '_id' not in r:
            report_error("Got a weird reply from elasticsearch.index(): %s.\n\nindex_name=%s\nid=%s\nbody=%s" % (r, index_name, doc['uid'], doc))

    except Exception as e:
        report_error("Failed to index item in Elasticsearch. Got error: %s\nindex_name=%s\nid=%s\nbody=%s" % (str(e), index_name, doc['uid'], doc))
        raise InternalServerError("Failed to index this item. Ksting admins are informed.")


def es_delete_doc(index_name, doc_type, uid):
    get_es().delete(
        index=index_name,
        doc_type=doc_type,
        id=uid,
        refresh=True,
        ignore=[404],
    )


#
# Get document
#

def es_get_doc(index_name, doc_type, uid):
    """Get a document from an elasticsearch index"""

    assert index_name
    assert uid

    es = get_es()

    try:
        doc = es.get(
            index=index_name,
            doc_type=doc_type,
            id=uid,
        )
        log.info("ES.index() returns %s" % doc)
    except exceptions.NotFoundError as e:
        log.warn("Item not found: %s" % str(e))
        raise ESItemNotFoundError("Item %s not found in ES index %s: %s" % (uid, index_name, str(e)))

    return doc


#
# Search index
#

def es_search_index(index_name=None, doc_type=None, sort=[], query=None, page=None, item_per_page=None):
    """Search the elasticsearch index and return hits"""

    if not page:
        page = 0

    if not query:
        query = ''

    esquery = {
        'from': page * item_per_page,
        'size': item_per_page,
        'sort': sort
    }

    query = query.strip()

    # Build es query
    if query == '':
        text_query = {"match_all": {}}
    else:
        text_query = {
            "match": {
                "free_search": {
                    "query": query,
                    "operator": "and"
                }
            }
        }


    esquery['query'] = text_query

    es = get_es()

    log.info("Searching %s for '%s'" % (index_name, query))
    try:
        res = es.search(
            index=index_name,
            doc_type=doc_type,
            body=esquery,
        )
        log.info("Found %s matches" % res['hits']['total'])
        return res

    except Exception as e:
        # If searching a test index, it may have been dropped by testaccept.common
        log.info("Caught: %s" % str(e))
        if '-test' in index_name and 'index_not_found_exception' in str(e):
            # Fake an empty hit
            log.info("This test index is missing. Faking no matches")
            return {'hits': {'hits': [], 'total': 0}}
        else:
            raise e


def get_all_docs(query, index_name, doc_type, batch_size=100):
    """Given an elasticsearch query, return all matching ES documents (can be a lot)"""

    es = get_es()

    log.info("Initializing scroll search for query: %s" % query)

    res = es.search(
        index=index_name,
        doc_type=doc_type,
        body=query,
        scroll='2m',
    )

    scroll_id = res['_scroll_id']
    log.info("scroll_id=%s" % scroll_id)

    if 'hits' not in res or len(res['hits']['hits']) == 0:
        return

    # Return those results
    for doc in res['hits']['hits']:
        yield doc

    # Now loop on results
    loop = True
    while loop:
        res = es.scroll(
            scroll='2m',
            scroll_id=scroll_id
        )

        for doc in res['hits']['hits']:
            yield doc

        if len(res['hits']['hits']) < batch_size:
            loop = False
