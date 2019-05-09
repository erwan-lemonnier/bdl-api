import logging
from pymacaron_core.swagger.apipool import ApiPool
from bdl.utils import mixin
from bdl.categories import get_categories, SOLD, BLACKLIST_ALL
from bdl.io.sqs import send_message
from bdl.io.comprehend import identify_language


log = logging.getLogger(__name__)


QUEUE_NAME = 'announces-to-parse'


def model_to_announce(o):
    """Take a bravado object and return an Announce"""
    if o.is_complete not in (True, False):
        o.is_complete = False
    mixin(o, Announce)


class Announce():

    def __str__(self):
        return '%s/%s (%s %s)' % (self.source, self.title, self.price, self.currency)


    def identify_language(self):
        """Use Amazon comprehend to identify the announce's language, prior to curation"""
        self.language = identify_language(self.text_content())


    def to_scraper_task(self):
        return ApiPool.bdl.model.ScraperTask(
            name=str(self),
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
