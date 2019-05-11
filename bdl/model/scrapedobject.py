import logging
from pymacaron_core.swagger.apipool import ApiPool
from bdl.utils import mixin
from bdl.io.sqs import send_message
from bdl.model.bdlitem import model_to_bdlitem
from bdl.model.item import create_item


log = logging.getLogger(__name__)


QUEUE_NAME = 'announces-to-parse'


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
        return '<ScrapedObject %s-%s/%s %s >' % (
            self.source,
            self.index,
            'real' if self.real else 'test',
            str(self._get_subitem()),
        )
    o.__class__.__str__ = str
    o.__class__.__repr__ = str
    o.__class__.__unicode__ = str


class ScrapedObject():

    def _get_subitem(self):
        if self.bdlitem:
            return self.bdlitem
        elif self.topmodel:
            return self.topmodel


    def validate_for_processing(self):
        """Make sure this scraped object contains all the data we need from it"""
        assert self.native_url, "Announce native_url is not set"
        assert self.is_complete in (True, False), "Announce is_complete is not set (%s)" % self.native_url
        self._get_subitem().validate_for_processing(self.native_url)


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


    def process(self, index=None, source=None, real=None):
        """Process this scraped object"""
        subitem = self._get_subitem()
        action = subitem.process(
            native_url=self.native_url,
            is_complete=self.is_complete,
        )
        assert action in ('SKIP', 'INDEX', 'QUEUE')

        if action == 'QUEUE':
            self.queue_up()
        elif action == 'INDEX':
            item = create_item(
                self,
                index=index,
                real=self.real,
                source=self.source,
            )
            log.info("New Item has item_id=%s" % item.item_id)
