import logging
import json
import os
from time import sleep
from boto.s3.key import Key
from pymacaron.test import PyMacaronTestCase
from pymacaron_core.swagger.apipool import ApiPool
from elasticsearch import exceptions
from bdl.io.s3 import get_s3_conn
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


    def process_items(self, *objects, **kwargs):
        """Post one or more scraped objects for processing"""
        data = {
            'index': 'BDL',
            'source': kwargs.get('source', 'TEST'),
            'real': False,
            'objects': objects,
        }
        synchronous = True if kwargs.get('synchronous', False) else False
        if synchronous:
            data['synchronous'] = True

        j = self.assertPostReturnJson(
            'v1/items/process',
            data,
            auth="Bearer %s" % self.token,
        )
        if not synchronous:
            self.assertEqual(j, {'results': []})
        return j


    def get_item_or_timeout(self, native_url=None):
        """Return an item as json, given its native_url. Or None"""
        if native_url:
            count = 0
            while True:
                item = get_item_by_native_url(native_url)

                if item:
                    j = ApiPool.bdl.model_to_json(item)
                    log.debug("Got item by native_url=%s: %s" % (native_url, json.dumps(j, indent=4)))
                    return j

                if count > 10:
                    log.debug("Failed to find item with native_url=%s" % native_url)
                    return None

                count = count + 1
                sleep(1)

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


    def get_es_item_or_timeout(self, item_id, index='BDL', real=True):
        count = 0
        while True:
            i = self.get_es_item(item_id, index=index, real=real)
            if i:
                return i

            if count > 10:
                log.debug("Failed to find item with item_id=%s" % item_id)
                return None

            count = count + 1
            sleep(1)


    def assertIsInES(self, item_id, real=True):
        j = self.get_es_item_or_timeout(item_id, real=real)
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


    def process_sold_announce(self, native_url=None, synchronous=None):
        """Post one sold announce with the given native_url"""
        if not native_url:
            native_url = self.native_test_url1
        return self.process_items(
            {
                'is_complete': False,
                'native_url': native_url,
                'bdlitem': {
                    'has_ended': True,
                    'is_sold': True,
                    'price_sold': 100,
                }
            },
            synchronous=synchronous,
        )


    def process_ended_announce(self, native_url=None, synchronous=None):
        """Post one ended announce with the given native_url"""
        if not native_url:
            native_url = self.native_test_url1
        return self.process_items(
            {
                'is_complete': False,
                'native_url': native_url,
                'bdlitem': {
                    'has_ended': True,
                }
            },
            synchronous=synchronous,
        )


    def process_incomplete_announce(self, native_url=None, title='foobar', price=1000, currency='SEK', synchronous=None):
        """Post an announce for sale but incomplete, with the given native_url"""
        if not native_url:
            native_url = self.native_test_url1
        return self.process_items(
            {
                'is_complete': False,
                'native_url': native_url,
                'bdlitem': {
                    'has_ended': False,
                    'title': title,
                    'price': price,
                    'currency': currency,
                },
            },
            synchronous=synchronous,
        )


    def process_complete_announce(self, native_url=None, title='foobar', price=1000, currency='SEK', description='barfoo', native_picture_url='https://img.bazardelux.com/cat2.jpg', language=None, synchronous=None):
        """Post an announce for sale with complete data, with the given native_url"""
        if not native_url:
            native_url = self.native_test_url1

        data = {
            'is_complete': True,
            'native_url': native_url,
            'bdlitem': {
                'has_ended': False,
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

        return self.process_items(data, synchronous=synchronous)


    def create_bdl_item(self, native_url=None, price=1000, currency='SEK', country='SE', price_is_fixed=False):
        if not native_url:
            native_url = self.native_test_url1
        self.process_items({
            'is_complete': True,
            'native_url': native_url,
            'bdlitem': {
                'has_ended': False,
                'language': 'en',
                'title': 'This is a test title',
                'description': 'A nice louis vuitton bag',
                'country': country,
                'price': price,
                'currency': currency,
                'price_is_fixed': price_is_fixed,
                'native_picture_url': 'https://img.bazardelux.com/cat2.jpg',
            },
        })

        j = self.get_item_or_timeout(native_url=native_url)
        log.debug("Created item: %s" % json.dumps(j, indent=4))
        self.assertIsItem(j, index='BDL')
        return j


    def assertIsItem(self, j, index='BDL', has_ended=False):
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

            if has_ended:
                self.assertEqual(j['bdlitem']['has_ended'], True)
                self.assertTrue(j['bdlitem']['date_ended'])
            else:
                self.assertEqual(j['bdlitem']['has_ended'], False)
                self.assertTrue('date_sold' not in j['bdlitem'])


    def cleanup_pictures(self, item_id):

        # Cleanup
        bucket = get_s3_conn().get_bucket('bdl-pictures')

        def delete_key(name):
            k = Key(bucket)
            k.key = name
            bucket.delete_key(k)

        delete_key('%s.jpg' % item_id)
        delete_key('%s_w200.jpg' % item_id)
        delete_key('%s_w400.jpg' % item_id)
        delete_key('%s_w600.jpg' % item_id)
