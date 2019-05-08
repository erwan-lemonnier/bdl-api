import logging
import json
from uuid import uuid4
from pymacaron_core.swagger.apipool import ApiPool
from pymacaron.utils import to_epoch, timenow
from pymacaron_dynamodb import get_dynamodb
from bdl.db.elasticsearch import es_index_doc_async, es_index_doc, es_delete_doc
from bdl.utils import mixin


log = logging.getLogger(__name__)


def model_to_item(o):
    """Take a bravado object and return a UserProfile"""
    mixin(o, Item, IndexableItem)

class Item():

    def generate_id(self):
        """Find an item_id that is not already taken"""
        from bdl.db.item import item_exists
        while not self.item_id:
            item_id = '%s-%s' % (self.index.lower(), str(uuid4()).replace('-', '')[0:30])
            log.debug("Generated item_id=%s" % item_id)
            if not item_exists(item_id):
                self.item_id = item_id

    def set_tags(self):
        """Set the item's category tags"""
        # TODO
        self.tags = []

    def set_slug(self):
        """Set the item's slug, which has to be unique"""
        # TODO
        self.slug = "-"

    def generate_searchable_string(self):
        """Generate the searchable_string for this item"""
        # TODO
        self.searchable_string = "-"

    def import_pictures(self):
        """Import the item's pictures and resize them"""
        # TODO
        self.picture_url_w400 = self.picture_url
        self.picture_url_w600 = self.picture_url

    def set_display_priority(self):
        # TODO
        self.display_priority = 1


    def archive(self):
        """Move this item from the items table into the items-archived table, and remove
        it from elasticsearch"""
        assert self.is_sold, "Only sold items may be archived"

        log.debug("Archiving item %s (%s)" % (self.item_id, self.slug))

        itemsold = ApiPool.bdl.model.ArchivedItem(
            **ApiPool.bdl.model_to_json(self)
        )
        itemsold.save_to_db()

        # Remove from dynamodb
        table = get_dynamodb().Table('items')
        table.delete_item(Key={'item_id': self.item_id})

        # And remove from elasticsearch
        es_delete_doc(
            self.get_es_index(),
            self.get_es_doc_type(),
            self.item_id,
        )


class IndexableItem():

    def get_es_doc_type(self):
        return 'ITEM_FOR_SALE'

    def get_es_index(self):
        return 'items-live' if self.real else 'items-test'

    def index_to_es(self, async=True):
        """Store this item into Elasticsearch"""

        doc = ApiPool.bdl.model_to_json(self)

        doc['free_search'] = self.searchable_string
        doc['epoch_created'] = to_epoch(self.date_created)
        doc['epoch_last_check'] = to_epoch(self.date_last_check)

        log.debug("Indexing item for sale with free_search: [%s]" % doc['free_search'])

        f = es_index_doc_async if async else es_index_doc
        r = f(
            self.get_es_index(),
            doc,
            self.get_es_doc_type(),
            self.item_id,
        )

        return r


def create_item(announce, item_id=None, index=None, real=False, source=None):
    assert index, "index (%s) is defined" % index
    assert source, "source (%s) is defined" % source
    assert real in (True, False), "real (%s) is true or false" % real

    announce_json = ApiPool.bdl.model_to_json(announce)
    log.debug("About to generate item from announce: %s" % json.dumps(announce_json, indent=4))

    # Make sure this announce contains the minimum amount of data
    required = [
        'title', 'description', 'country', 'price',
        'price_is_fixed', 'currency', 'native_url', 'picture_url',
    ]
    for k in required:
        assert hasattr(announce, k) and getattr(announce, k) is not None, "Announce has undefined attribute %s" % k

    # Create a new item
    now = timenow()

    item = ApiPool.bdl.model.Item(**announce_json)
    model_to_item(item)

    if item_id:
        item.item_id = item_id
    else:
        item.generate_id()

    item.index = index
    item.real = real
    item.source = source
    item.date_created = now
    item.date_last_check = now
    item.count_views = 0
    item.is_sold = False

    # Make totally sure test items don't make it into live indexes
    if item.source == 'TEST':
        item.real = False

    item.set_tags()
    item.set_slug()
    item.generate_searchable_string()
    item.set_display_priority()
    item.import_pictures()

    item.save_to_db(async=False)

    return item
