import logging
import json
import dateutil.parser
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
    if o.bdlitem:
        from bdl.model.bdlitem import model_to_bdlitem
        if type(o.bdlitem) is dict:
            o.bdlitem = ApiPool.bdl.json_to_model('BDLItem', o.bdlitem)
        model_to_bdlitem(o.bdlitem)
    elif o.topmodel:
        raise Exception('model_to_topmodel not implemented')

    # Monkey patch __str__
    def str(self):
        subitem = ": %s " % self.get_subitem() if hasattr(self, 'get_subitem') else ''
        return "<Item %s%s>" % (
            self.item_id,
            subitem,
        )

    o.__class__.__str__ = str
    o.__class__.__repr__ = str
    o.__class__.__unicode__ = str


class Item():

    def get_subitem(self):
        """Return the scraped object stored in this item"""

        if self.bdlitem:
            return self.bdlitem
        elif self.topmodel:
            return self.topmodel


    # def get_text(self):
    #     return self.get_subitem().get_text()


    def set_item_id(self):
        """Find an item_id that is not already taken"""

        assert self.source

        source_to_prefix = {
            'FACEBOOK': 'fb',
            'BLOCKET': 'bl',
            'EBAY': 'eb',
            'TRADERA': 'tr',
            'LEBONCOIN': 'lbc',
            'CITYBOARD': 'ctb',
            'SHPOCK': 'spk',
            'TEST': 'tst',
        }

        log.debug("item source: %s" % self.source)
        from bdl.db.item import item_exists
        while not self.item_id:
            item_id = '%s-%s' % (
                source_to_prefix[self.source],
                str(uuid4()).replace('-', '')[0:10],
            )
            if not item_exists(item_id):
                log.debug("Generated item_id=%s" % item_id)
                self.item_id = item_id


    def regenerate(self, update_picture=False, async=False):
        """Regenerate all non-static attributes in this Item and its subitem"""

        log.info("Re-generating all non-static item attributes")
        subitem = self.get_subitem()
        subitem.regenerate(update_picture=update_picture)
        self.slug = subitem.get_slug(item_id=self.item_id)
        self.searchable_string = subitem.get_searchable_string(self)
        self.display_priority = subitem.get_display_priority()
        self.save_to_db(async=async)


    def archive(self):
        """Move this item from the items table into the items-archived table, and remove
        it from elasticsearch"""

        assert self.bdlitem.is_sold, "Only sold BDL items may be archived"

        log.debug("Archiving item %s (%s)" % (self.item_id, self.slug))

        archiveditem = ApiPool.bdl.model.ArchivedItem(
            **ApiPool.bdl.model_to_json(self)
        )
        model_to_item(archiveditem)

        # BUG: the above transformation looses the encoding of datetimes
        # A proper fix would be to use: ApiPool.bdl.json_to_model('ArchivedItem', ApiPool.bdl.model_to_json(self))
        # but that breaks database persistence (save_to_db() is not monkey patched...)
        archiveditem.date_created = dateutil.parser.parse(archiveditem.date_created)
        archiveditem.date_last_check = dateutil.parser.parse(archiveditem.date_last_check)
        archiveditem.save_to_db()

        # Remove from dynamodb
        table = get_dynamodb().Table('items')
        table.delete_item(Key={'item_id': self.item_id})

        # And remove from elasticsearch
        es_delete_doc(
            self.get_es_index(),
            self.get_es_doc_type(),
            self.item_id,
        )

    def update(self, newsubitem):
        self.get_subitem().update(self, newsubitem)


class IndexableItem():

    def get_es_doc_type(self):
        return self.get_subitem().doc_type(),


    def get_es_index(self):
        return '%s-%s' % (
            self.get_subitem().index_name(),
            'live' if self.real else 'test',
        )


    def index_to_es(self, async=True):
        """Store this item into Elasticsearch"""

        doc = ApiPool.bdl.model_to_json(self)

        doc['free_search'] = self.searchable_string
        doc['epoch_created'] = to_epoch(self.date_created)
        doc['epoch_last_check'] = to_epoch(self.date_last_check)

        log.debug("Indexing %s with free_search: [%s]" % (
            self.get_es_doc_type(),
            doc['free_search'],
        ))

        f = es_index_doc_async if async else es_index_doc
        r = f(
            self.get_es_index(),
            doc,
            self.get_es_doc_type(),
            self.item_id,
        )

        return r


def create_item(sobj, index=None, source=None, real=False):
    """Take a ScrappedObject and generate an Item, save and return it"""

    assert index, "index (%s) is defined" % index
    assert source, "source (%s) is defined" % source
    assert real in (True, False), "real (%s) is true or false" % real

    sobj_json = ApiPool.bdl.model_to_json(sobj)
    log.debug("About to generate Item from sobj: %s" % json.dumps(sobj_json, indent=4))

    # Make sure this scrapped object contains the minimum amount of data
    assert sobj.native_url, 'Scraped object has no native_url'
    assert sobj.is_complete in (True, False), 'Scraped object\'s is_complete is not True or False'
    sobj.get_subitem().validate_for_indexing()

    # Create a new item
    now = timenow()

    # Remove some ScrappedObject attributes that are not passed to Items
    for k in ('is_complete', ):
        if k in sobj_json:
            del sobj_json[k]

    item = ApiPool.bdl.model.Item(**sobj_json)
    model_to_item(item)

    item.index = index
    item.real = real
    item.source = source
    item.date_created = now
    item.date_last_check = now
    item.count_views = 0

    item.set_item_id()

    # Make totally sure test items don't make it into live indexes
    if item.source == 'TEST':
        item.real = False

    item.regenerate(update_picture=True)
    log.info("Created new Item %s (%s)" % (item.item_id, item.slug))

    return item
