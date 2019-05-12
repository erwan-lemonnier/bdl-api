import os
import imp
import logging
from bdl.db.item import get_item_by_native_url


common = imp.load_source('common', os.path.join(os.path.dirname(__file__), 'common.py'))


log = logging.getLogger(__name__)


class Tests(common.BDLTests):

    def test_v1_items_process__auth_required(self):
        self.assertPostReturnError(
            'v1/items/process',
            {'source': 'TEST', 'index': 'BDL', 'objects': []},
            401,
            'AUTHORIZATION_HEADER_MISSING',
        )


    def test_v1_items_process__invalid_data(self):
        tests = [
            # Generic scraped object(s) validation
            [{}, 400, 'INVALID_PARAMETER', "'source' is a required property"],
            [{'source': 'TEST'}, 400, 'INVALID_PARAMETER', "'index' is a required property"],
            [{'source': 'TEST', 'index': 'BDL'}, 400, 'INVALID_PARAMETER', "'objects' is a required property"],
            [{'source': 'TEST', 'index': 'BDL', 'objects': [{}]}, 400, 'INVALID_PARAMETER', "'is_complete' is a required property"],
            [{'source': 'TEST', 'index': 'BDL', 'objects': [{'is_complete': True}]}, 400, 'INVALID_PARAMETER', "'native_url' is a required property"],
            [{'source': 'TEST', 'index': 'BDL', 'objects': [{'is_complete': True, 'native_url': 'bob'}]}, 400, 'INVALID_PARAMETER', "scraped object has no subitem"],

            # BDL item sold
            [{'source': 'TEST', 'index': 'BDL', 'objects': [{'is_complete': False, 'native_url': 'bob', 'bdlitem': {}}]}, 400, 'INVALID_PARAMETER', "'is_sold' is a required property"],

            # BDL item not sold and incomplete
            [{'source': 'TEST', 'index': 'BDL', 'objects': [{'is_complete': False, 'native_url': 'bob', 'bdlitem': {'is_sold': False}}]}, 400, 'INVALID_PARAMETER', "BDL item has no title"],
            [{'source': 'TEST', 'index': 'BDL', 'objects': [{'is_complete': False, 'native_url': 'bob', 'bdlitem': {'is_sold': False, 'title': 'foo'}}]}, 400, 'INVALID_PARAMETER', "BDL item has no price"],
            [{'source': 'TEST', 'index': 'BDL', 'objects': [{'is_complete': False, 'native_url': 'bob', 'bdlitem': {'is_sold': False, 'title': 'foo', 'price': 100}}]}, 400, 'INVALID_PARAMETER', "BDL item has no currency"],

            # # BDL item not sold and complete
            [{'source': 'TEST', 'index': 'BDL', 'objects': [{'is_complete': True, 'native_url': 'bob', 'bdlitem': {'is_sold': False}}]}, 400, 'INVALID_PARAMETER', "BDL item has no title"],
            [{'source': 'TEST', 'index': 'BDL', 'objects': [{'is_complete': True, 'native_url': 'bob', 'bdlitem': {'is_sold': False, 'title': 'foo'}}]}, 400, 'INVALID_PARAMETER', "BDL item has no price"],
            [{'source': 'TEST', 'index': 'BDL', 'objects': [{'is_complete': True, 'native_url': 'bob', 'bdlitem': {'is_sold': False, 'title': 'foo', 'price': 100}}]}, 400, 'INVALID_PARAMETER', "BDL item has no currency"],
            [{'source': 'TEST', 'index': 'BDL', 'objects': [{'is_complete': True, 'native_url': 'bob', 'bdlitem': {'is_sold': False, 'title': 'foo', 'price': 100, 'currency': 'SEK'}}]}, 400, 'INVALID_PARAMETER', "BDL item has no description"],
            [{'source': 'TEST', 'index': 'BDL', 'objects': [{'is_complete': True, 'native_url': 'bob', 'bdlitem': {'is_sold': False, 'title': 'foo', 'price': 100, 'currency': 'SEK', 'description': 'd'}}]}, 400, 'INVALID_PARAMETER', "BDL item has no native_picture_url"],
            [{'source': 'TEST', 'index': 'BDL', 'objects': [{'is_complete': True, 'native_url': 'bob', 'bdlitem': {'is_sold': False, 'title': 'foo', 'price': 100, 'currency': 'SEK', 'description': 'd', 'native_picture_url': 'n'}}]}, 400, 'INVALID_PARAMETER', "BDL item has no country"],
        ]

        for data, status, error, msg in tests:
            j = self.assertPostReturnError(
                'v1/items/process',
                data,
                status,
                error,
                auth="Bearer %s" % self.token
            )
            self.assertTrue(msg in j['error_description'])


    def test_v1_items_process__bdl__no_announce(self):
        sources = [
            'FACEBOOK', 'BLOCKET', 'EBAY', 'TRADERA', 'LEBONCOIN',
            'CITYBOARD', 'SHPOCK', 'TEST'
        ]

        for source in sources:
            self.assertPostReturnOk(
                'v1/items/process',
                {
                    'source': 'TEST',
                    'index': 'BDL',
                    'objects': [],
                },
                auth='Bearer %s' % self.token,
            )


    def test_v1_items_process__bdl__sold_announce(self):
        self.cleanup()
        url = self.native_test_url1
        self.assertEqual(get_item_by_native_url(url), None)

        # First, no announce exists - No item gets archived
        self.process_sold_announce(native_url=url)
        self.assertEqual(get_item_by_native_url(url), None)

        # Create that item
        j = self.create_bdl_item(native_url=url)
        self.assertEqual(j['bdlitem']['is_sold'], False)
        self.assertTrue('date_sold' not in j['bdlitem'])
        self.assertTrue('price_sold' not in j['bdlitem'])
        self.assertIsInES(j['item_id'], real=False)

        # Now process that announce as sold, again
        self.process_sold_announce(native_url=url)
        jj = self.get_item(native_url=url)

        self.assertTrue(jj['date_sold'])
        j['bdlitem']['is_sold'] = True
        j['bdlitem']['date_sold'] = jj['date_sold']
        self.assertEqual(jj, j)

        self.assertIsNotInES(j['item_id'], real=False)


    def test_v1_items_process__bdl__incomplete_announce__rejected(self):
        self.cleanup()
        url = self.native_test_url1

        # Announce with a title that fails first curation
        self.process_incomplete_announce(native_url=url, title='wont match anything')
        self.assertEqual(get_item_by_native_url(url), None)

        # Announce with a price that fails first curation
        self.process_incomplete_announce(native_url=url, title='louis vuitton', price=0)
        self.assertEqual(get_item_by_native_url(url), None)


    def test_v1_items_process__bdl__complete_announce__rejected(self):
        self.cleanup()
        url = self.native_test_url1

        # Announce with a title that fails deep curation, with no language to force an amazon comprehend call
        self.process_complete_announce(native_url=url, title='wont match anything', description='nothing to match', price=1234)
        self.assertEqual(get_item_by_native_url(url), None)

        # Same, but set a language
        self.process_complete_announce(native_url=url, title='wont match anything', description='nothing to match', price=1234, language='en')
        self.assertEqual(get_item_by_native_url(url), None)


    def test_v1_items_process__bdl__incomplete_announce__accepted(self):
        # TODO: load one announce with only limited data that pass the curator. Check that it enters the scraper queue
        pass

    def test_v1_items_process__bdl__complete_announce__accepted(self):
        self.cleanup()
        url = self.native_test_url1

        # This announce is complete and passes curation
        self.process_complete_announce(native_url=url, title='louis vuitton', description='nice bag', price=1000)
        j = self.get_item(native_url=url)
        self.assertEqual(j, {
            'count_views': 0,
            'date_created': j['date_created'],
            'date_last_check': j['date_created'],
            'display_priority': 1,
            'index': 'BDL',
            'item_id': j['item_id'],
            'native_url': 'https://bdl.com/test1',
            'real': False,
            'searchable_string': j['searchable_string'],
            'slug': 'louis-vuitton_1000_SEK__%s' % j['item_id'],
            'source': 'TEST',
            'bdlitem': {
                'country': 'SE',
                'currency': 'SEK',
                'description': 'nice bag',
                'is_sold': False,
                'language': 'fr',
                'native_picture_url': 'boo',
                'picture_tags': [],
                'picture_url': 'boo',
                'picture_url_w400': 'boo',
                'picture_url_w600': 'boo',
                'price': 1000.0,
                'price_is_fixed': False,
                'tags': j['bdlitem']['tags'],
                'title': 'louis vuitton',
            },
        })

        # Send the announce again, but change price. Check that the item got updated
        self.process_complete_announce(native_url=url, title='louis vuitton', description='nice bag', price=800)
        jj = self.get_item(native_url=url)
        j['bdlitem']['price'] = 800
        j['slug'] = 'louis-vuitton_800_SEK__%s' % j['item_id']
        self.assertEqual(jj, j)
