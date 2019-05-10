import logging
import json
import os
from pymacaron.test import PyMacaronTestCase
from pymacaron_core.swagger.apipool import ApiPool
from elasticsearch import exceptions
from bdl.formats import get_custom_formats
from bdl.utils import gen_jwt_token
from bdl.io.es import get_es
from bdl.db.elasticsearch import es_delete_doc
from bdl.db.item import PersistentItem
from bdl.db.item import PersistentArchivedItem
from bdl.db.item import get_item_by_native_url


log = logging.getLogger(__name__)


class BDLTests(PyMacaronTestCase):

    def setUp(self):
        super().setUp()
        self.maxDiff = None
        self.token = gen_jwt_token(type='test')

        self.native_test_url1 = 'https://bdl.com/test1'
        self.native_test_url2 = 'https://bdl.com/test2'


    def tearDown(self):
        super().tearDown()


    def load_api(self):
        ApiPool.add(
            'bdl',
            yaml_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'apis', 'bdl.yaml'),
            formats=get_custom_formats(),
        )


    def cleanup(self):
        self.load_api()
        for url in (self.native_test_url1, self.native_test_url2):
            item = get_item_by_native_url(url)
            if item:
                PersistentItem.get_table().delete_item(Key={'item_id': item.item_id})
                PersistentArchivedItem.get_table().delete_item(Key={'item_id': item.item_id})

                for index in ('items-test', 'items-live'):
                    es_delete_doc(
                        index,
                        'ITEM_FOR_SALE',
                        item.item_id,
                    )


    def _call_announce_process(self, *announces):
        """Post one or more announces for processing"""
        self.assertPostReturnOk(
            'v1/announces/process',
            {
                'index': 'BDL',
                'source': 'TEST',
                'real': False,
                'announces': announces,
            },
            auth="Bearer %s" % self.token,
        )


    def process_sold_announce(self, native_url=None):
        """Post one sold announce with the given native_url"""
        if not native_url:
            native_url = self.native_test_url1
        self._call_announce_process({
            'is_sold': True,
            'native_url': native_url,
        })


    def process_incomplete_announce(self, native_url=None, title='foobar', price=1000, currency='SEK'):
        """Post an announce for sale but incomplete, with the given native_url"""
        if not native_url:
            native_url = self.native_test_url1
        self._call_announce_process({
            'is_sold': False,
            'is_complete': False,
            'native_url': native_url,
            'title': title,
            'price': price,
            'currency': currency,
        })


    def process_complete_announce(self, native_url=None, title='foobar', price=1000, currency='SEK', description='barfoo', native_picture_url='boo', language=None):
        """Post an announce for sale with complete data, with the given native_url"""
        if not native_url:
            native_url = self.native_test_url1

        data = {
            'is_sold': False,
            'is_complete': True,
            'native_url': native_url,
            'title': title,
            'price': price,
            'currency': currency,
            'description': description,
            'native_picture_url': native_picture_url,
            'country': 'SE',
        }

        if language:
            data['language'] = language

        self._call_announce_process(data)


    def create_item(self, native_url=None, price=1000, currency='SEK', country='SE', price_is_fixed=False):
        if not native_url:
            native_url = self.native_test_url1
        self._call_announce_process({
            'is_complete': True,
            'is_sold': False,
            'language': 'en',
            'index': 'BDL',
            'real': False,
            'source': 'TEST',
            'title': 'This is a test title',
            'description': 'A nice louis vuitton bag',
            'country': country,
            'price': price,
            'currency': currency,
            'price_is_fixed': price_is_fixed,
            'native_url': native_url,
            'native_picture_url': 'bob',
        })

        j = self.get_item(native_url=native_url)
        log.debug("Created item: %s" % json.dumps(j, indent=4))
        self.assertIsItem(j)
        return j


    def get_item(self, native_url=None):
        """Return an item as json, given its native_url. Or None"""
        if native_url:
            item = get_item_by_native_url(native_url)
            if not item:
                return None
            return ApiPool.bdl.model_to_json(item)
        else:
            assert 0, 'Not implemented'


    def assertIsItem(self, j, is_sold=False):
        required = [
            'item_id', 'index', 'title', 'description', 'country', 'price',
            'price_is_fixed', 'currency', 'native_url', 'real',
            'searchable_string',
            'date_created', 'date_last_check',
            'count_views',
            'display_priority',
            'tags', 'picture_tags',
            'picture_url', 'picture_url_w400', 'picture_url_w600',
        ]

        for k in required:
            self.assertTrue(k in j, "Item has no attribute %s" % k)

        if is_sold:
            self.assertEqual(j['is_sold'], True)
            self.assertTrue(j['date_sold'])
        else:
            self.assertEqual(j['is_sold'], False)
            self.assertTrue('date_sold' not in j)


    def get_es_item(self, item_id, real=True):
        index_name = 'items-live' if real else 'items-test'
        try:
            doc = get_es().get(
                index=index_name,
                doc_type='ITEM_FOR_SALE',
                id=item_id,
            )
            log.info("Found elasticsearch document: %s" % json.dumps(doc, indent=4))
            return doc['_source']
        except exceptions.NotFoundError as e:
            log.warn("Item not found: %s" % str(e))
            return None


    def assertIsInES(self, item_id, real=True):
        j = self.get_es_item(item_id, real=real)
        self.assertEqual(j['item_id'], item_id)

    def assertIsNotInES(self, item_id, real=True):
        j = self.get_es_item(item_id, real=real)
        self.assertEqual(j, None)

    def assertIsInItemTable(self, item_id):
        self.assertTrue('Item' in PersistentItem.get_table().get_item(Key={'item_id': item_id}))

    def assertIsNotInItemTable(self, item_id):
        self.assertTrue('Item' not in PersistentItem.get_table().get_item(Key={'item_id': item_id}))

    def assertIsInItemArchive(self, item_id):
        self.assertTrue('Item' in PersistentArchivedItem.get_table().get_item(Key={'item_id': item_id}))

    def assertIsNotInItemArchive(self, item_id):
        self.assertTrue('Item' not in PersistentArchivedItem.get_table().get_item(Key={'item_id': item_id}))
