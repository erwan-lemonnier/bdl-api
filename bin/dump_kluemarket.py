import os
import sys
import json
import logging
import click
import flask

log = logging.getLogger(__name__)
app = flask.Flask(__name__)

PATH_LIBS = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..')
sys.path.append(PATH_LIBS)

from bdl.io.es import get_es

INDEX_ARCHIVE = 'items-archived-live'
INDEX_FORSALE = 'items-forsale-live'


def get_all(index, doc_type):
    es = get_es(
        host='search-kluesearch-g6dmxzzuvvzpms2yjrlvvuk5ku.eu-west-1.es.amazonaws.com',
        aws_access_key_id='..',
        aws_secret_access_key='..',
        aws_region='eu-west-1',
    )
    index_name = index

    body = {
        "query": {
            "range": {
                "count_views": {
                    "gte": 15,
                }
            }
        }
    }

    log.info("Querying with: %s" % body)

    # Initialize the scroll
    page = es.search(
        index=index_name,
        doc_type=doc_type,
        search_type='scan',
        scroll='2m',
        size=1000,
        body=body,
    )

    sid = page['_scroll_id']
    scroll_size = page['hits']['total']

    hits = []

    # Start scrolling
    while (scroll_size > 0):
        page = es.scroll(scroll_id=sid, scroll='2m')
        sid = page['_scroll_id']
        scroll_size = len(page['hits']['hits'])

        for doc in page['hits']['hits']:
            body = doc['_source']
            # print("FOUND %s" % json.dumps(body, indent=4))

            hits.append(body)

            item_id = body['uid']
            assert '-' in item_id, "assert fail on item_id=%s" % item_id
            with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'kluemarket', item_id), "w") as f:
                f.write(json.dumps(body, indent=4))

    return hits


@click.command()
def main():

    hits = []

    # Generate all dates during this month
    # hits.extend(get_all('items-sold-live', 'SOLD_ITEM'))
    hits.extend(get_all('items-forsale-live', 'FORSALE_ITEM'))
    hits.extend(get_all('items-forsale-live', 'SOLD_ITEM'))
    hits.extend(get_all('items-archived-live', 'FORSALE_ITEM'))

    log.info("Found %s items" % (len(hits)))

    # for i in hits:
    #     print("%s;%s;%s;%s;" % (i['date_created'], i['price'], i['tags'], i['origin_url']))


if __name__ == "__main__":
    with app.test_request_context(''):
        main()
