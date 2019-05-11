import logging
from pymacaron_core.swagger.apipool import ApiPool
from pymacaron.utils import timenow
from bdl.utils import mixin
from bdl.categories import get_categories, SOLD, BLACKLIST_ALL
from bdl.io.sqs import send_message
from bdl.io.comprehend import identify_language
from bdl.db.item import get_item_by_native_url
from bdl.model.item import create_item


log = logging.getLogger(__name__)


QUEUE_NAME = 'announces-to-parse'


def model_to_announce(o):
    """Take a bravado object and return an Announce"""
    if o.is_complete not in (True, False):
        o.is_complete = False
    mixin(o, Announce)

    # Monkey patch __str__
    def str(self):
        return '<%s/%s (%s %s)>' % (self.source, self.title, self.price, self.currency)
    o.__class__.__str__ = str
    o.__class__.__repr__ = str
    o.__class__.__unicode__ = str


class Announce():

    def identify_language(self):
        """Use Amazon comprehend to identify the announce's language, prior to curation"""
        self.language = identify_language(self.text_content())


    def to_scraper_task(self):
        return ApiPool.bdl.model.ScraperTask(
            goal='SCRAP_ANNOUNCE',
            source=self.source,
            scraper_data=self.scraper_data,
            native_url=self.native_url,
            native_doc_id=self.native_doc_id,
            native_group_id=self.native_group_id,
        )


    def queue_up(self):
        """Queue up this announce to be completely parsed later on"""
        log.info("Queuing up announce '%s' for deep scraping" % str(self))
        send_message(
            QUEUE_NAME,
            ApiPool.bdl.model_to_json(self.to_scraper_task()),
        )

    # ----------------------------------------
    #
    #   Curation rules
    #
    # ----------------------------------------

    def text_content(self):
        s = self.title
        if self.description:
            s = s + ' ' + self.description
        return s


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
        return SOLD.match(self.text_content(), self.language)


    def pass_curator(self, ignore_whitelist=False, skip_sold=True):
        """Curate an announce, based on simple heuristics"""

        log.info("Curating '%s'" % self.title)

        text = self.text_content()

        if skip_sold and self.seems_sold():
            return False

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


    def process(self, index=None):
        """Process this announce, ie check if it is sold, incomplete or complete, and
        decide whether to create a new item, update an existing item, remove an
        existing item associated to it, or queue up the announce for further
        scraping

        """

        assert index in ('BDL', )
        assert self.source in ('FACEBOOK', 'BLOCKET', 'TRADERA', 'TEST')
        assert self.real in (True, False)

        # If the announce is sold, we need to archive it
        if self.is_sold:
            log.info("Announce is sold [%s]" % str(self))
            item = get_item_by_native_url(self.native_url)

            if not item:
                log.info("There is NO item based on this announce - Ignoring it")
                return

            log.info("Found item %s based on this announce - Archiving it" % item.item_id)
            item.is_sold = True
            item.date_sold = timenow()
            if hasattr(self, 'price_sold') and self.price_sold:
                log.info("Setting item's price_sold: %s" % self.price_sold)
                item.price_sold = self.price_sold
            item.archive()
            return

        # If no language is specified, use amazon comprehend to identify the
        # announce's language. We need the language to match against keyword
        # lists
        if not self.language:
            self.identify_language()
            log.info("Identified announce's language: %s [%s]" % (self.language, str(self)))

        # If the announce is incompletely parsed, we may want to schedule it
        # for complete parsing
        if not self.is_complete:
            log.info("Announce is not complete [%s]" % str(self))

            # Let's decide if we queue it up for complete scraping, or if we
            # just drop it

            if not self.pass_curator(ignore_whitelist=True):
                log.info("Announce failed 1st curation - Skipping it [%s]" % str(self))
                return
            else:
                log.info("Announce passed 1st curation - Queuing it up [%s]" % str(self))
                self.queue_up()
                return

        # This announce has all the data we can ever scraped. This is
        # the real deal: is it going to pass thorough curation?

        if not self.pass_curator():
            log.info("Announce failed deep curation - Skipping it [%s]" % str(self))
            return

        log.info("Announce passed deep curation [%s]" % str(self))

        # Is there already an item associated with this announce?
        item = get_item_by_native_url(self.native_url)
        if item:
            log.info("Announce is already indexed as item %s [%s]" % (item.item_id, str(self)))
            item.update(self)
            return

        # There is no item associated with this announce: create one!
        log.info("Creating new Item for announce [%s]" % str(self))
        item = create_item(
            self,
            index=index,
            real=self.real,
            source=self.source,
        )
        log.info("Item has item_id %s" % item.item_id)
        return
