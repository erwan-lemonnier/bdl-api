import logging
from pymacaron_core.swagger.apipool import ApiPool
from bdl.exceptions import InvalidDataError
from bdl.utils import mixin
from bdl.model.bdlitem import model_to_bdlitem
from bdl.model.item import create_item


log = logging.getLogger(__name__)


def model_to_scraped_object(o):
    """Take a bravado object and return an Announce"""
    if o.is_complete not in (True, False):
        o.is_complete = False
    mixin(o, ScrapedObject)
    if o.bdlitem:
        model_to_bdlitem(o.bdlitem)
    elif o.topmodel:
        raise Exception('model_to_topmodel not implemented')

    # Monkey patch __str__
    def str(self):
        subitem = " %s " % self.get_subitem() if hasattr(self, 'get_subitem') else ''
        return '<ScrapedObject %s%s>' % (
            self.native_url,
            subitem,
        )
    o.__class__.__str__ = str
    o.__class__.__repr__ = str
    o.__class__.__unicode__ = str


class ScrapedObject():

    def get_subitem(self):
        if self.bdlitem:
            return self.bdlitem
        elif self.topmodel:
            return self.topmodel


    def validate_for_processing(self):
        """Make sure this scraped object contains all the data we need from it"""
        if not self.bdlitem and not self.topmodel:
            raise InvalidDataError('scraped object has no subitem')
        self.get_subitem().validate_for_processing(
            native_url=self.native_url,
            is_complete=self.is_complete,
        )


    def to_scraper_task(self, source):
        assert source
        return ApiPool.bdl.model.ScraperTask(
            goal='SCRAP_URL',
            source=source,
            scraper_data=self.scraper_data,
            native_url=self.native_url,
        )


    def queue_for_scraping(self, source=None):
        """Queue up this announce to be completely parsed later on"""
        log.info("Queuing up announce '%s' for deep scraping" % str(self))

        assert source

        # Post an url scraping task to the BDL scraper where it will be queued
        # up for later processing
        log.info("Posting scrape request to BDL scraper for %s" % self.native_url)
        ApiPool.scraper.client.scrape_page(
            ApiPool.scraper.model.ScrapeSettings(
                source=source,
                native_url=self.native_url,
            )
        )


    def process(self, index=None, source=None, real=None):
        """Process this scraped object. Call the subitem's process() method and expect
        one of 5 possible commands back, and optionally an item upon which to
        act:

        - SKIP: ignore this object
        - INDEX: create an item for this object and index it into elasticsearch
        - SCRAPE: re-scrape this object
        - UPDATE: update an existing item with the scraped object's subitem
        - ARCHIVE: archive the found item

        """

        assert index is not None
        assert real in (True, False)
        assert source is not None

        subitem = self.get_subitem()
        action, item = subitem.process(
            native_url=self.native_url,
            is_complete=self.is_complete,
        )

        assert action in ('SKIP', 'INDEX', 'UPDATE', 'SCRAPE', 'ARCHIVE')
        item_id = item.item_id if item else None

        log.info("Performing ACTION: %s (item_id=%s)" % (action, item_id))

        if action == 'SCRAPE':
            self.queue_for_scraping(source=source)

        elif action == 'ARCHIVE':
            assert item, "Got action ARCHIVE but no item for %s" % str(self)
            item.archive()

        elif action == 'UPDATE':
            assert item, "Got action UPDATE but no item for %s" % str(self)
            log.info("BOOM?")
            item.update(self.get_subitem())

        elif action == 'INDEX':
            item = create_item(
                self,
                index=index,
                real=real,
                source=source,
            )
            log.info("Created new Item with item_id=%s" % item.item_id)

        elif action == 'SKIP':
            log.info("Skipping %s" % self.native_url)

        else:
            assert 0, "Huh? Don't know what to do with action %s" % action

        return action, item_id
