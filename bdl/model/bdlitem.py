import logging
import re
from unidecode import unidecode
from pymacaron.utils import timenow
from s3imageresizer import S3ImageResizer
from bdl.io.s3 import get_s3_conn
from bdl.exceptions import InvalidDataError
from bdl.utils import mixin
from bdl.utils import cleanup_string
from bdl.utils import html_to_unicode
from bdl.tagger import get_matching_tags
from bdl.categories import get_categories
from bdl.db.item import get_item_by_native_url
from bdl.io.comprehend import identify_language
from bdl.categories import SOLD, BLACKLIST_ALL


log = logging.getLogger(__name__)


def model_to_bdlitem(o):
    """Take a bravado object or ES dict and return a BDLItem"""
    mixin(o, BDLItem)

    # Make sure numbers are integers
    if hasattr(o, 'price') and o.price:
        o.price = int(o.price)
    if hasattr(o, 'price_sold') and o.price_sold:
        o.price_sold = int(o.price_sold)
    if hasattr(o, 'epoch_published') and o.epoch_published:
        o.epoch_published = int(o.epoch_published)

    # Monkey patch __str__
    def str(self):
        if not self.title:
            return '<BDLItem>'
        return "<BDLItem '%s%s'%s>" % (
            self.title[0:20], '..' if len(self.title) > 20 else '',
            ' %s %s' % (self.price, self.currency) if self.price and self.currency else '',
        )
    o.__class__.__str__ = str
    o.__class__.__repr__ = str
    o.__class__.__unicode__ = str


class BDLItem():
    """An announce on bazardelux"""

    def index_name(self):
        return 'bdlitems'


    def doc_type(self):
        return 'BDL_ITEM'


    def validate_for_processing(self, native_url=None, is_complete=None):
        assert native_url
        assert is_complete in (True, False)
        required = []
        if not self.has_ended:
            required = required + ['title', 'price', 'currency']
        if is_complete:
            required = required + ['description', 'native_picture_url', 'country']
        for k in required:
            if getattr(self, k) is None:
                raise InvalidDataError('BDL item has no %s (%s)' % (k, native_url))
        if self.price_is_fixed not in (True, False):
            self.price_is_fixed = False


    def validate_for_indexing(self):
        """Make sure this BDLItem contains all the data we need for indexing it"""
        required = [
            'title', 'description', 'price', 'language', 'country',
            'price_is_fixed', 'currency', 'native_picture_url',
        ]
        for k in required:
            assert hasattr(self, k) and getattr(self, k) is not None, "has undefined attribute %s" % k


    def get_text(self):
        """Return all the text parts of this item, in one concatenated string"""
        s = ''
        if self.title:
            s = s + ' %s ' % self.title
        if self.description:
            s = s + ' %s ' % self.description
        return s


    def identify_language(self):
        """Use Amazon comprehend to identify the announce's language, prior to curation"""
        self.language = identify_language(self.get_text())


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


    def get_slug(self, item_id=None):
        """Set the item's slug, which has to be unique"""
        assert item_id
        s = unidecode(html_to_unicode(self.title))
        s = re.sub('[^0-9a-zA-Z]+', '-', s)
        s = re.sub('[-]+', '-', s)
        s = s.strip('-')
        s = '%s_%s_%s__%s' % (s, self.price, self.currency, item_id)
        return s


    def get_searchable_string(self, item):
        """Generate the searchable_string for this item"""
        assert item.item_id

        l = [
            cleanup_string(self.title) if self.title else '',
            cleanup_string(self.description) if self.description else '',
            'SOURCE_%s' % item.source,
            cleanup_string(self.location) if self.location else '',
            'COUNTRY_%s' % self.country,
            'CURRENCY_%s' % self.currency,
            'FIXED_PRICE' if self.price_is_fixed else '',
            self.native_doc_id if self.native_doc_id else '',
            self.native_seller_id if self.native_seller_id else '',
            self.native_group_id if self.native_group_id else '',
            item.item_id,
        ]

        for t in self.tags:
            l.append(':%s:' % t.upper())

        s = ' '.join(l)
        s = re.sub(r'\s+', ' ', s)
        return s


    def regenerate(self, item_id=None, update_picture=False):
        """Regenerate attributes after an update or being created"""
        assert item_id
        self.set_tags()
        if update_picture:
            self.import_pictures(item_id=item_id)
            self.set_picture_tags()


    def import_pictures(self, item_id=None):
        """Import the item's pictures and resize them"""

        assert item_id

        CLOUDFRONT_URL = 'https://img.bazardelux.com'
        S3_PICTS_BUCKET = 'bdl-pictures'

        i = S3ImageResizer(get_s3_conn())

        # First, upload picture to s3
        log.info("Fetching picture %s" % self.native_picture_url)
        i.fetch(self.native_picture_url)

        metadata = {
            'item_id': item_id,
            'picture_url': self.native_picture_url,
            'Expires': 'Sun, 03 May 2095 23:02:37 GMT',
        }

        # Store it to S3
        log.info("Saving raw picture to S3")
        i.store(
            in_bucket=S3_PICTS_BUCKET,
            key_name='%s.jpg' % item_id,
            metadata=metadata,
        )

        def resize_and_store(i, width, metadata):
            key_name = '%s_w%s.jpg' % (item_id, width)
            i.resize(
                width=width
            ).store(
                in_bucket=S3_PICTS_BUCKET,
                key_name=key_name,
                metadata=metadata,
            )
            return CLOUDFRONT_URL + '/' + key_name

        self.picture_url = '%s/%s.jpg' % (CLOUDFRONT_URL, item_id)
        self.picture_url_w200 = resize_and_store(i, 200, metadata)
        self.picture_url_w400 = resize_and_store(i, 400, metadata)
        self.picture_url_w600 = resize_and_store(i, 600, metadata)


    def get_display_priority(self):
        # TODO: call rekognition on the picture, and the fewer categories, the higher the score
        return 1


    def mark_as_ended(self, subitem=None):
        """Mark an item as ended. Optionally take a scraped object's subitem containing
        a date_ended, is_sold, price sold and date_sold

        """
        log.info("Marking BDLItem as ended: %s" % self)
        self.has_ended = True
        self.date_ended = timenow()

        if subitem:
            for a in ['date_ended', 'is_sold', 'price_sold', 'date_sold']:
                if hasattr(subitem, a) and getattr(subitem, a) is not None:
                    log.debug("Setting %s = %s" % (a, getattr(subitem, a)))
                    setattr(self, a, getattr(subitem, a))

        if self.is_sold and not self.date_sold:
            self.date_sold = self.date_ended


    def update(self, item, obj):
        """Take an updated scrapedobject for this item and see if anything relevant
        (title, description, price, etc) has changed. If so, update the item
        and save it.

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
            if hasattr(obj, k) and getattr(obj, k):
                if not hasattr(self, k) or (hasattr(self, k) and getattr(self, k) != getattr(obj, k)):
                    log.info("Updating Item %s" % k)
                    setattr(self, k, getattr(obj, k))
                    updated = True

        # If the picture has changed, also update it
        if self.native_picture_url != obj.native_picture_url:
            updated = True
            update_picture = True
            log.info("Updating picture of Item %s" % item.item_id)
            self.native_picture_url = obj.native_picture_url

        # Re-generate this item
        if updated:
            log.info("BDLItem has changed %s" % str(self))
            item.regenerate(update_picture=update_picture)

        log.debug("BDLItem is now %s" % str(self))


    # ----------------------------------------
    #
    #   Curation rules
    #
    # ----------------------------------------


    def has_ok_price(self, price_ranges=None):
        """Check that the price and currency look reasonable"""
        minmax = {
            # currency: [min_price, max_price]
            'SEK': [400, 100000],
            'EUR': [40, 10000],
            'USD': [40, 10000],
            'GBP': [40, 10000],
        }

        if price_ranges:
            assert type(price_ranges) is list
            for o in price_ranges:
                minmax[o.currency.upper()] = [o.price_min, o.price_max]

        if self.currency not in minmax:
            raise Exception("Curator has no price interval defined for currency %s (announce: %s)" % (self.currency, self))

        min_price, max_price = minmax[self.currency]
        if self.price < min_price:
            log.info("Item price is under %s %s" % (min_price, self.currency))
            return False
        if self.price > max_price:
            log.info("Item price is over %s %s" % (max_price, self.currency))
            return False

        if '1234' in str(self.price):
            log.info("Item price contains %s" % '1234')
            return False

        return True


    def seems_sold(self):
        """Check whether it says in the announce that the item is sold already"""
        return SOLD.match(self.get_text(), self.language)


    def pass_curator(self, ignore_whitelist=False, skip_sold=True):
        """Curate an announce, based on simple heuristics"""

        log.info("Curating '%s'" % self.title)

        text = self.get_text()

        # If no language is specified, use amazon comprehend to identify the
        # announce's language. We need the language to match against keyword
        # lists
        if not self.language:
            self.identify_language()
            log.info("Identified announce's language: %s [%s]" % (self.language, str(self)))

        if skip_sold and self.seems_sold():
            return False

        # TODO: check if we have already parsed and rejected this announce
        # earlier on by matching native_url against a cache of recently
        # rejected native_urls

        if BLACKLIST_ALL.match(text, self.language):
            log.debug("Announce fails global blacklist check")
            return False

        for cat in get_categories():
            # cat has attributes whitelist, blacklist, prices and name
            if not self.has_ok_price(price_ranges=cat.prices):
                log.debug("Announce fails price check on category %s" % cat.name)
                continue
            elif cat.blacklist.match(text, self.language):
                log.debug("Announce fails blacklist check on category %s" % cat.name)
                continue
            elif not ignore_whitelist and not cat.whitelist.match(text, self.language):
                log.debug("Announce fails whitelist check on category %s" % cat.name)
                continue

            # Yipii! Announce passes all checks on this category
            log.debug("Announce passes all checks on category %s" % cat.name)
            return True

        # No category matches...
        return False

    # ----------------------------------------
    #
    #   Announce processing logic
    #
    # ----------------------------------------


    def process(self, native_url=None, is_complete=None):
        """Process this scraped object, ie check if it is sold, incomplete or complete,
        and decide whether to create a new item, update an existing item,
        remove an existing item associated to it, or queue up the announce for
        further scraping

        """

        assert native_url
        assert is_complete in (True, False)

        # If the announce has ended, we need to archive it
        if self.has_ended:
            log.info("Announce has ended [%s]" % str(self))
            item = get_item_by_native_url(native_url)

            if not item:
                log.info("There is NO item based on this announce - Ignoring it")
                return 'SKIP', None

            log.info("Found item %s based on this announce - Archiving it" % item.item_id)
            item.get_subitem().mark_as_ended()
            # TODO: set is_sold, price_sold and date_sold if available
            return 'ARCHIVE', item

        # If the announce is incompletely parsed, we may want to schedule it
        # for complete parsing
        if not is_complete:
            log.info("Announce is not complete [%s]" % str(self))

            # Let's decide if we queue it up for complete scraping, or if we
            # just drop it

            if not self.pass_curator(ignore_whitelist=True):
                log.info("Announce failed 1st curation - Skipping it [%s]" % str(self))
                return 'SKIP', None
            else:
                log.info("Announce passed 1st curation - Queuing it up [%s]" % str(self))
                return 'SCRAPE', None

        # This announce has all the data we can ever scrape. This is
        # the real deal: is it going to pass thorough curation?

        if not self.pass_curator():
            log.info("Announce failed deep curation - Skipping it [%s]" % str(self))
            return 'SKIP', None

        log.info("Announce passed deep curation [%s]" % str(self))

        # Is there already an item associated with this announce?
        item = get_item_by_native_url(native_url)
        if item:
            log.info("Announce is already indexed as item %s [%s]" % (item.item_id, str(self)))
            return 'UPDATE', item

        # There is no item associated with this announce: create one!
        log.info("Creating new Item for announce [%s]" % str(self))
        return 'INDEX', None
