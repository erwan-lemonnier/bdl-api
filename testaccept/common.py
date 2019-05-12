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


    def process_items(self, *objects):
        """Post one or more scraped objects for processing"""
        self.assertPostReturnOk(
            'v1/items/process',
            {
                'index': 'BDL',
                'source': 'TEST',
                'real': False,
                'objects': objects,
            },
            auth="Bearer %s" % self.token,
        )


    def get_item(self, native_url=None):
        """Return an item as json, given its native_url. Or None"""
        if native_url:
            item = get_item_by_native_url(native_url)
            if not item:
                return None
            j = ApiPool.bdl.model_to_json(item)
            log.debug("Got item by native_url=%s: %s" % (native_url, json.dumps(j, indent=4)))
            return j
        else:
            assert 0, 'Not implemented'


    def get_es_item(self, item_id, index='BDL', real=True):
        index_name = None
        doc_type = None
        if index == 'BDL':
            index_name = 'bdlitems-live' if real else 'bdlitems-test'
            doc_type = 'BDL_ITEM'
        assert doc_type, "Don't know doc_type for index %s" % index

        try:
            doc = get_es().get(
                index=index_name,
                doc_type=doc_type,
                id=item_id,
            )
            log.info("Found elasticsearch document: %s" % json.dumps(doc, indent=4))
            return doc['_source']
        except exceptions.NotFoundError as e:
            log.warn("Item not found: %s" % str(e))
            return None


    def assertIsInES(self, item_id, real=True):
        j = self.get_es_item(item_id, real=real)
        assert j, "Failed to find item %s in ES" % item_id
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


    #
    # Specific to BDL
    #

    def process_sold_announce(self, native_url=None):
        """Post one sold announce with the given native_url"""
        if not native_url:
            native_url = self.native_test_url1
        self.process_items({
            'is_complete': False,
            'native_url': native_url,
            'bdlitem': {
                'is_sold': True,
            }
        })


    def process_incomplete_announce(self, native_url=None, title='foobar', price=1000, currency='SEK'):
        """Post an announce for sale but incomplete, with the given native_url"""
        if not native_url:
            native_url = self.native_test_url1
        self.process_items({
            'is_complete': False,
            'native_url': native_url,
            'bdlitem': {
                'is_sold': False,
                'title': title,
                'price': price,
                'currency': currency,
            },
        })


    def process_complete_announce(self, native_url=None, title='foobar', price=1000, currency='SEK', description='barfoo', native_picture_url='boo', language=None):
        """Post an announce for sale with complete data, with the given native_url"""
        if not native_url:
            native_url = self.native_test_url1

        data = {
            'is_complete': True,
            'native_url': native_url,
            'bdlitem': {
                'is_sold': False,
                'title': title,
                'price': price,
                'currency': currency,
                'description': description,
                'native_picture_url': native_picture_url,
                'country': 'SE',
            },
        }

        if language:
            data['bdlitem']['language'] = language

        self.process_items(data)


    def create_bdl_item(self, native_url=None, price=1000, currency='SEK', country='SE', price_is_fixed=False):
        if not native_url:
            native_url = self.native_test_url1
        self.process_items({
            'is_complete': True,
            'native_url': native_url,
            'bdlitem': {
                'is_sold': False,
                'language': 'en',
                'title': 'This is a test title',
                'description': 'A nice louis vuitton bag',
                'country': country,
                'price': price,
                'currency': currency,
                'price_is_fixed': price_is_fixed,
                'native_picture_url': 'bob',
            },
        })

        j = self.get_item(native_url=native_url)
        log.debug("Created item: %s" % json.dumps(j, indent=4))
        self.assertIsItem(j, index='BDL')
        return j


    def assertIsItem(self, j, index='BDL', is_sold=False):
        required = [
            'item_id', 'index', 'slug', 'native_url', 'real',
            'searchable_string', 'date_created', 'date_last_check',
            'count_views', 'display_priority'
        ]

        for k in required:
            self.assertTrue(k in j, "Item has no attribute %s" % k)

        if index == 'BDL':
            required = [
                'title', 'description', 'country', 'price',
                'price_is_fixed', 'currency',
                'tags', 'picture_tags',
                'picture_url', 'picture_url_w400', 'picture_url_w600',
            ]
            for k in required:
                self.assertTrue(k in j['bdlitem'], "Item has no attribute %s" % k)

            if is_sold:
                self.assertEqual(j['bdlitem']['is_sold'], True)
                self.assertTrue(j['bdlitem']['date_sold'])
            else:
                self.assertEqual(j['bdlitem']['is_sold'], False)
                self.assertTrue('date_sold' not in j['bdlitem'])
