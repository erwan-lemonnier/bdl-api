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
            [{'source': 'TEST', 'index': 'BDL', 'objects': [{'is_complete': False, 'native_url': 'bob', 'bdlitem': {}}]}, 400, 'INVALID_PARAMETER', "'has_ended' is a required property"],

            # BDL item not sold and incomplete
            [{'source': 'TEST', 'index': 'BDL', 'objects': [{'is_complete': False, 'native_url': 'bob', 'bdlitem': {'has_ended': False}}]}, 400, 'INVALID_PARAMETER', "BDL item has no title"],
            [{'source': 'TEST', 'index': 'BDL', 'objects': [{'is_complete': False, 'native_url': 'bob', 'bdlitem': {'has_ended': False, 'title': 'foo'}}]}, 400, 'INVALID_PARAMETER', "BDL item has no price"],
            [{'source': 'TEST', 'index': 'BDL', 'objects': [{'is_complete': False, 'native_url': 'bob', 'bdlitem': {'has_ended': False, 'title': 'foo', 'price': 100}}]}, 400, 'INVALID_PARAMETER', "BDL item has no currency"],

            # # BDL item not sold and complete
            [{'source': 'TEST', 'index': 'BDL', 'objects': [{'is_complete': True, 'native_url': 'bob', 'bdlitem': {'has_ended': False}}]}, 400, 'INVALID_PARAMETER', "BDL item has no title"],
            [{'source': 'TEST', 'index': 'BDL', 'objects': [{'is_complete': True, 'native_url': 'bob', 'bdlitem': {'has_ended': False, 'title': 'foo'}}]}, 400, 'INVALID_PARAMETER', "BDL item has no price"],
            [{'source': 'TEST', 'index': 'BDL', 'objects': [{'is_complete': True, 'native_url': 'bob', 'bdlitem': {'has_ended': False, 'title': 'foo', 'price': 100}}]}, 400, 'INVALID_PARAMETER', "BDL item has no currency"],
            [{'source': 'TEST', 'index': 'BDL', 'objects': [{'is_complete': True, 'native_url': 'bob', 'bdlitem': {'has_ended': False, 'title': 'foo', 'price': 100, 'currency': 'SEK'}}]}, 400, 'INVALID_PARAMETER', "BDL item has no description"],
            [{'source': 'TEST', 'index': 'BDL', 'objects': [{'is_complete': True, 'native_url': 'bob', 'bdlitem': {'has_ended': False, 'title': 'foo', 'price': 100, 'currency': 'SEK', 'description': 'd'}}]}, 400, 'INVALID_PARAMETER', "BDL item has no native_picture_url"],
            [{'source': 'TEST', 'index': 'BDL', 'objects': [{'is_complete': True, 'native_url': 'bob', 'bdlitem': {'has_ended': False, 'title': 'foo', 'price': 100, 'currency': 'SEK', 'description': 'd', 'native_picture_url': 'n'}}]}, 400, 'INVALID_PARAMETER', "BDL item has no country"],
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
            j = self.assertPostReturnJson(
                'v1/items/process',
                {
                    'source': source,
                    'index': 'BDL',
                    'objects': [],
                },
                auth='Bearer %s' % self.token,
            )
            self.assertEqual(j, {'results': []})


    def test_v1_items_process__bdl__sold_announce(self):
        self.cleanup()
        url = self.native_test_url1
        self.assertEqual(get_item_by_native_url(url), None)

        # First, no announce exists - No item gets archived
        r = self.process_sold_announce(native_url=url, synchronous=True)
        self.assertEqual(r, {'results': [{'action': 'SKIP'}]})

        # Create that item
        j = self.create_bdl_item(native_url=url)
        item_id = j['item_id']
        self.assertEqual(j['bdlitem']['has_ended'], False)
        self.assertTrue('date_ended' not in j['bdlitem'])
        self.assertTrue('date_sold' not in j['bdlitem'])
        self.assertTrue('price_sold' not in j['bdlitem'])
        self.assertIsInES(item_id, real=False)

        # Now process that announce as sold, again
        r = self.process_sold_announce(native_url=url, synchronous=True)
        self.assertEqual(r, {'results': [{'action': 'ARCHIVE', 'item_id': item_id}]})

        jj = self.get_item_or_timeout(native_url=url)
        self.assertTrue(jj['bdlitem']['date_ended'])
        self.assertTrue(jj['bdlitem']['date_sold'])
        j['bdlitem']['has_ended'] = True
        j['bdlitem']['is_sold'] = True
        j['bdlitem']['price_sold'] = 100
        j['bdlitem']['date_ended'] = jj['bdlitem']['date_ended']
        j['bdlitem']['date_sold'] = jj['bdlitem']['date_ended']
        self.assertEqual(jj, j)

        self.assertIsNotInES(j['item_id'], real=False)


    def test_v1_items_process__bdl__ended_announce(self):
        self.cleanup()
        url = self.native_test_url1
        self.assertEqual(get_item_by_native_url(url), None)

        # Create that item
        j = self.create_bdl_item(native_url=url)
        item_id = j['item_id']
        self.assertEqual(j['bdlitem']['has_ended'], False)
        self.assertTrue('date_ended' not in j['bdlitem'])
        self.assertTrue('date_sold' not in j['bdlitem'])
        self.assertTrue('price_sold' not in j['bdlitem'])
        self.assertIsInES(item_id, real=False)

        # Now process that announce as sold, again
        r = self.process_ended_announce(native_url=url, synchronous=True)
        self.assertEqual(r, {'results': [{'action': 'ARCHIVE', 'item_id': item_id}]})

        jj = self.get_item_or_timeout(native_url=url)
        self.assertTrue(jj['bdlitem']['date_ended'])
        self.assertTrue('date_sold' not in jj['bdlitem'])
        self.assertTrue('is_sold' not in jj['bdlitem'])
        j['bdlitem']['has_ended'] = True
        j['bdlitem']['date_ended'] = jj['bdlitem']['date_ended']
        self.assertEqual(jj, j)

        self.assertIsNotInES(j['item_id'], real=False)


    def test_v1_items_process__bdl__incomplete_announce__rejected(self):
        self.cleanup()
        url = self.native_test_url1

        # Announce with a title that fails first curation
        r = self.process_incomplete_announce(
            native_url=url,
            title='ikea totally sucks',
            synchronous=True,
        )
        self.assertEqual(r, {'results': [{'action': 'SKIP'}]})

        # Announce with a price that fails first curation
        r = self.process_incomplete_announce(
            native_url=url,
            title='louis vuitton',
            price=0,
            synchronous=True,
        )
        self.assertEqual(r, {'results': [{'action': 'SKIP'}]})


    def test_v1_items_process__bdl__complete_announce__rejected(self):
        self.cleanup()
        url = self.native_test_url1

        # Announce with a title that fails deep curation, with no language to force an amazon comprehend call
        r = self.process_complete_announce(
            native_url=url,
            title='wont match anything',
            description='nothing to match',
            price=1234,
            synchronous=True,
        )
        self.assertEqual(r, {'results': [{'action': 'SKIP'}]})

        # Same, but set a language
        r = self.process_complete_announce(
            native_url=url,
            title='wont match anything',
            description='nothing to match',
            price=1234,
            language='en',
            synchronous=True,
        )
        self.assertEqual(r, {'results': [{'action': 'SKIP'}]})


    def test_v1_items_process__bdl__incomplete_announce__accepted(self):
        self.cleanup()
        url = self.native_test_url1

        # Using a TEST BDL announce, that will be sent to the BDL scraper for
        # scraping and ignored there
        r = self.process_incomplete_announce(
            native_url=url,
            title='Louis Vuitton Speedy väska',
            price=2000,
            currency='SEK',
            synchronous=True,
        )

        # Check that the announce was queued up for scraping
        self.assertEqual(r, {'results': [{'action': 'SCRAPE'}]})


    def test_v1_items_process__bdl__complete_announce__accepted(self):
        self.cleanup()
        url = self.native_test_url1

        # This announce is complete and passes curation
        self.process_complete_announce(
            native_url=url,
            title='louis vuitton',
            description='nice bag',
            price=1000,
        )

        # Make sure it really was indexed
        j = self.get_item_or_timeout(native_url=url)
        item_id = j['item_id']
        self.assertEqual(j, {
            'count_views': 0,
            'date_created': j['date_created'],
            'date_last_check': j['date_created'],
            'display_priority': 1,
            'index': 'BDL',
            'item_id': item_id,
            'native_url': 'https://bdl.com/test1',
            'real': False,
            'searchable_string': j['searchable_string'],
            'slug': 'louis-vuitton_1000_SEK__%s' % j['item_id'],
            'source': 'TEST',
            'bdlitem': {
                'country': 'SE',
                'currency': 'SEK',
                'description': 'nice bag',
                'has_ended': False,
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
        r = self.process_complete_announce(
            native_url=url,
            title='louis vuitton',
            description='nice bag',
            price=800,
            synchronous=True,
        )

        self.assertEqual(
            r,
            {
                "results": [
                    {
                        "action": "UPDATE",
                        "item_id": item_id,
                    }
                ]
            }
        )

        jj = self.get_item_or_timeout(native_url=url)
        j['bdlitem']['price'] = 800
        j['slug'] = 'louis-vuitton_800_SEK__%s' % j['item_id']
        self.assertEqual(jj, j)
