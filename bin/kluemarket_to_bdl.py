#!/usr/bin/env python3
import os
import sys
import json
import logging
import click
from dateutil.parser import parse
from pymacaron_core.swagger.apipool import ApiPool
from pymacaron.config import get_config


log = logging.getLogger(__name__)


log.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
# formatter = logging.Formatter('%(message)s')
# handler.setFormatter(formatter)
log.addHandler(handler)
logging.getLogger('urllib3.connectionpool').setLevel(logging.INFO)


PATH_LIBS = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..')
sys.path.append(PATH_LIBS)

from bdl.formats import get_custom_formats
from bdl.model.item import model_to_item

config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'pym-config.yaml')
get_config(config_path)


@click.command()
@click.option('--item-id', required=True, metavar='ITEM_ID', help="Item ID to import to BDL")
def main(item_id):
    """Take a kluemarket item dump generated with dump_kluemarket.py and inject it into BDL

    """

    ApiPool.add(
        'api',
        yaml_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'apis', 'api.yaml'),
        formats=get_custom_formats(),
    )

    j = {}
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'kluemarket', item_id)) as f:
        s = f.read()
        j = json.loads(s)

    log.debug("About to import item %s" % json.dumps(j, indent=4))

    source = j['source'].upper()
    assert source in ('BLOCKET', 'TRADERA', 'FACEBOOK')

    date_created = parse(j['date_created'])
    item_id = j['uid']
    assert '-' in item_id

    doc_id = None
    if 'blocket_id' in j:
        doc_id = j['blocket_id']
    if 'tradera_id' in j:
        doc_id = j['tradera_id']

    location = None
    if 'blocket_location' in j:
        location = j['blocket_location']
    if 'tradera_location' in j:
        location = j['tradera_location']

    has_ended = True if 'is_archived' in j and j['is_archived'] else False
    archive_date = parse(j['archive_date']) if 'archive_date' in j else None

    i = ApiPool.api.model.Item(
        item_id=item_id,
        index='BDL',
        real=True,
        source=j['source'].upper(),
        native_url=j['origin_url'],
        count_views=j['count_views'],
        slug='-',
        date_created=date_created,
        date_last_check=date_created,
        bdlitem=ApiPool.api.model.BDLItem(
            title=j['title'],
            description=j['description'],
            country='SE',
            language='sv',
            price=j['price'],
            price_is_fixed=False,
            currency=j['currency'],
            has_ended=has_ended,
            date_ended=archive_date,
            is_sold=has_ended,
            epoch_published=j['epoch_created'],
            native_doc_id=doc_id,
            native_location=location,
            native_picture_url=j['s3_picture_url'],
        )
    )

    log.info("New item is: %s" % json.dumps(ApiPool.api.model_to_json(i), indent=4))

    model_to_item(i)

    i.regenerate(update_picture=True)

    if i.bdlitem.has_ended:
        i.archive()

    log.info("New item is: %s" % i)


if __name__ == "__main__":
    main()
