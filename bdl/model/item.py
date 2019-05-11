import logging
import json
import re
from uuid import uuid4
from unidecode import unidecode
from pymacaron_core.swagger.apipool import ApiPool
from pymacaron.utils import to_epoch, timenow
from pymacaron_dynamodb import get_dynamodb
from bdl.db.elasticsearch import es_index_doc_async, es_index_doc, es_delete_doc
from bdl.utils import mixin
from bdl.utils import cleanup_string
from bdl.utils import html_to_unicode
from bdl.tagger import get_matching_tags
from bdl.categories import get_categories


log = logging.getLogger(__name__)


def model_to_item(o):
    """Take a bravado object and return a UserProfile"""
    mixin(o, Item, IndexableItem)

    # Monkey patch __str__
    def str(self):
        return "<Item %s: '%s%s'%s>" % (
            self.item_id,
            self.title[0:20], '..' if len(self.title) > 20 else '',
            ' %s %s' % (self.price, self.currency) if self.price and self.currency else '',
        )
    o.__class__.__str__ = str
    o.__class__.__repr__ = str
    o.__class__.__unicode__ = str


class Item():

    def get_text(self):
        """Return all the text parts of this item, in one concatenated string"""
        s = ''
        if self.title:
            s = s + ' %s ' % self.title
        if self.description:
            s = s + ' %s ' % self.description
        return s


    def generate_id(self):
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


    def set_tags(self, reset=False):
        """Set the item's category tags, by matching the announce's text against keywords"""
        item_tags = []

        if not reset and self.tags:
            item_tags = self.tags

        text = self.get_text()

        # Find top categories that match this item
        for cat in get_categories():
            tags = cat.get_matching_words(text, self.language)
            if len(tags) > 0:
                item_tags = item_tags + [t for t in tags] + [cat.name.upper()]

        # Find all tags/categories that match this item
        tags = get_matching_tags(text)
        if len(tags) > 0:
            item_tags = item_tags + [t for t in tags]

        log.debug("Tags are: %s" % item_tags)

        self.tags = sorted(list(set(item_tags)))
        log.info("Tagged item with %s" % self.tags)


    def set_picture_tags(self):
        """Use Amazon rekognition to identify the main objects in the picture, and
        store them as picture tags
        """
        # TODO: set picture tags
        self.picture_tags = []


    def set_slug(self):
        """Set the item's slug, which has to be unique"""

        s = unidecode(html_to_unicode(self.title))
        s = re.sub('[^0-9a-zA-Z]+', '-', s)
        s = re.sub('[-]+', '-', s)
        s = s.strip('-')
        s = '%s_%s_%s__%s' % (s, self.price, self.currency, self.item_id)

        self.slug = s


    def generate_searchable_string(self):
        """Generate the searchable_string for this item"""
        assert self.item_id

        l = [
            cleanup_string(self.title) if self.title else '',
            cleanup_string(self.description) if self.description else '',
            'SOURCE_%s' % self.source,
            cleanup_string(self.location) if self.location else '',
            'COUNTRY_%s' % self.country,
            'CURRENCY_%s' % self.currency,
            'FIXED_PRICE' if self.price_is_fixed else '',
            self.native_doc_id if self.native_doc_id else '',
            self.native_seller_id if self.native_seller_id else '',
            self.native_group_id if self.native_group_id else '',
            self.item_id,
        ]

        for t in self.tags:
            l.append(':%s:' % t.upper())

        s = ' '.join(l)
        s = re.sub(r'\s+', ' ', s)
        self.searchable_string = s


    def import_pictures(self):
        """Import the item's pictures and resize them"""
        # TODO: import item pictures to S3 and resize them
        self.picture_url = self.native_picture_url
        self.picture_url_w400 = self.native_picture_url
        self.picture_url_w600 = self.native_picture_url


    def set_display_priority(self):
        # TODO: call rekognition on the picture, and the fewer categories, the higher the score
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


    def regenerate(self, update_picture=False, async=False):
        """Regenerate all non-static attributes in this Item"""
        log.info("Re-generating all non-static item attributes")
        self.set_tags()
        self.set_slug()
        self.generate_searchable_string()
        if update_picture:
            self.import_pictures()
            self.set_picture_tags()
        self.set_display_priority()
        self.save_to_db(async=async)


    def update(self, announce):
        """Take an updated announce for this item and see if anything relevant (title,
        description, price, etc) has changed. If so, update the item and save it
        """

        updated = False
        update_picture = False

        # These are the attributes to update in the item if they have changed
        # NOTE: we should absolutly not update the native_url
        attributes = [
            'title', 'description', 'price', 'currency', 'language', 'country',
            'location', 'price_is_fixed', 'native_doc_id', 'native_seller_id',
            'native_seller_name', 'native_seller_is_shop', 'native_group_id',
            'native_location',
        ]

        for k in attributes:
            if hasattr(announce, k) and getattr(announce, k):
                if not hasattr(self, k) or (hasattr(self, k) and getattr(self, k) != getattr(announce, k)):
                    log.info("Updating %s of Item %s" % (k, self.item_id))
                    setattr(self, k, getattr(announce, k))
                    updated = True

        # If the picture has changed, also update it
        if self.native_picture_url != announce.native_picture_url:
            updated = True
            update_picture = True
            log.info("Updating picture of Item %s" % self.item_id)
            self.native_picture_url = announce.native_picture_url

        # Re-generate this item
        if updated:
            log.info("Item has changed %s" % str(self))
            self.regenerate(update_picture=update_picture)

        log.debug("Item is now %s" % str(self))


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
        'title', 'description', 'price', 'language', 'country',
        'price_is_fixed', 'currency', 'native_url', 'native_picture_url',
    ]
    for k in required:
        assert hasattr(announce, k) and getattr(announce, k) is not None, "Announce has undefined attribute %s" % k

    # Create a new item
    now = timenow()

    # Cleanup some announce data that shouldn't be passed on to the item
    for k in ('is_complete', ):
        if k in announce_json:
            del announce_json[k]

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

    item.regenerate(update_picture=True)
    log.info("Created new Item %s (%s)" % (item.item_id, item.slug))

    return item
