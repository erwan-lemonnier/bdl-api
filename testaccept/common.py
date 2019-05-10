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
from bdl.db.item import PersistentItem, PersistentArchivedItem


log = logging.getLogger(__name__)


class BDLTests(PyMacaronTestCase):

    def setUp(self):
        super().setUp()
        self.maxDiff = None
        self.token = gen_jwt_token(type='test')

        self.item_id1 = 'test-0000001'
        self.item_id2 = 'test-0000002'


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
        for item_id in (self.item_id1, self.item_id2):
            PersistentItem.get_table().delete_item(Key={'item_id': item_id})
            PersistentArchivedItem.get_table().delete_item(Key={'item_id': item_id})

            for index in ('items-test', 'items-live'):
                es_delete_doc(
                    index,
                    'ITEM_FOR_SALE',
                    item_id,
                )


    def create_item(self, item_id=None, price=1000, currency='SEK', country='SE', price_is_fixed=False):
        if not item_id:
            item_id = self.item_id1
        j = self.assertPostReturnJson(
            'v1/announce',
            {
                'is_complete': True,
                'is_sold': False,
                'language': 'en',
                'item_id': item_id,
                'index': 'BDL',
                'real': False,
                'source': 'TEST',
                'title': 'This is a test title',
                'description': 'This i a test description',
                'country': country,
                'price': price,
                'currency': currency,
                'price_is_fixed': price_is_fixed,
                'native_url': 'bob',
                'picture_url': 'bob',
            },
            auth="Bearer %s" % self.token,
        )
        self.assertIsItem(j)
        return j


    def assertIsItem(self, j, is_sold=False):
        required = [
            'item_id', 'index', 'title', 'description', 'country', 'price',
            'price_is_fixed', 'currency', 'native_url', 'real',
            'searchable_string',
            'date_created', 'date_last_check',
            'count_views',
            'display_priority',
            'tags',
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
        self.assertTrue('Item' in PersistentItem.get_table().get_item(Key={'item_id': self.item_id1}))

    def assertIsNotInItemTable(self, item_id):
        self.assertTrue('Item' not in PersistentItem.get_table().get_item(Key={'item_id': self.item_id1}))

    def assertIsInItemArchive(self, item_id):
        self.assertTrue('Item' in PersistentArchivedItem.get_table().get_item(Key={'item_id': self.item_id1}))

    def assertIsNotInItemArchive(self, item_id):
        self.assertTrue('Item' not in PersistentArchivedItem.get_table().get_item(Key={'item_id': self.item_id1}))
