import logging
from pymacaron_core.swagger.apipool import ApiPool
from bdl.exceptions import InvalidDataError
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
        subitem = "%s" % self.get_subitem()
        return '<ScrapedObject %s %s >' % (
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


    def queue_up(self, source=None):
        """Queue up this announce to be completely parsed later on"""
        log.info("Queuing up announce '%s' for deep scraping" % str(self))
        task = self.to_scraper_task(source)
        send_message(
            QUEUE_NAME,
            ApiPool.bdl.model_to_json(task),
        )


    def process(self, index=None, source=None, real=None):
        """Process this scraped object"""
        assert index is not None
        assert real in (True, False)
        assert source is not None

        subitem = self.get_subitem()
        action = subitem.process(
            native_url=self.native_url,
            is_complete=self.is_complete,
        )
        assert action in ('SKIP', 'INDEX', 'QUEUE')

        if action == 'QUEUE':
            self.queue_up(source=source)

        elif action == 'INDEX':
            item = create_item(
                self,
                index=index,
                real=real,
                source=source,
            )
            log.info("New Item has item_id=%s" % item.item_id)
