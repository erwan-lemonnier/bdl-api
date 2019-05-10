import os
import imp
import logging
from bdl.db.item import get_item_by_native_url


common = imp.load_source('common', os.path.join(os.path.dirname(__file__), 'common.py'))


log = logging.getLogger(__name__)


class Tests(common.BDLTests):

    def test_v1_announces_process__auth_required(self):
        self.assertPostReturnError(
            'v1/announces/process',
            {'source': 'TEST', 'announces': []},
            401,
            'AUTHORIZATION_HEADER_MISSING',
        )


    def test_v1_announces_process__invalid_data(self):
        tests = [
            [{}, 400, 'INVALID_PARAMETER', "'source' is a required property"],
            [{'source': 'TEST'}, 400, 'INVALID_PARAMETER', "'announces' is a required property"],

            # Announce sold
            [{'source': 'TEST', 'announces': [{'is_sold': True}]}, 400, 'INVALID_PARAMETER', "'native_url' is a required property"],
            [{'source': 'TEST', 'announces': [{'native_url': 'bob'}]}, 400, 'INVALID_PARAMETER', "'is_sold' is a required property"],

            # Announce not sold and incomplete
            [{'source': 'TEST', 'announces': [{'is_sold': False, 'native_url': 'bob'}]}, 500, 'UNHANDLED_SERVER_ERROR', "Announce is_complete is not set"],
            [{'source': 'TEST', 'announces': [{'is_sold': False, 'native_url': 'bob', 'is_complete': False}]}, 500, 'UNHANDLED_SERVER_ERROR', "Announce title is not set"],
            [{'source': 'TEST', 'announces': [{'is_sold': False, 'native_url': 'bob', 'is_complete': False, 'title': 'foobar'}]}, 500, 'UNHANDLED_SERVER_ERROR', "Announce price is not set"],
            [{'source': 'TEST', 'announces': [{'is_sold': False, 'native_url': 'bob', 'is_complete': False, 'title': 'foobar', 'price': 0}]}, 500, 'UNHANDLED_SERVER_ERROR', "Announce currency is not set"],

            # Announce not sold and complete
            [{'source': 'TEST', 'announces': [{'is_sold': False, 'native_url': 'bob', 'is_complete': True}]}, 500, 'UNHANDLED_SERVER_ERROR', "Announce title is not set"],
            [{'source': 'TEST', 'announces': [{'is_sold': False, 'native_url': 'bob', 'is_complete': True, 'title': 'foobar'}]}, 500, 'UNHANDLED_SERVER_ERROR', "Announce price is not set"],
            [{'source': 'TEST', 'announces': [{'is_sold': False, 'native_url': 'bob', 'is_complete': True, 'title': 'foobar', 'price': 0}]}, 500, 'UNHANDLED_SERVER_ERROR', "Announce currency is not set"],
            [{'source': 'TEST', 'announces': [{'is_sold': False, 'native_url': 'bob', 'is_complete': True, 'title': 'foobar', 'price': 0, 'currency': 'SEK'}]}, 500, 'UNHANDLED_SERVER_ERROR', "Announce description is not set"],
            [{'source': 'TEST', 'announces': [{'is_sold': False, 'native_url': 'bob', 'is_complete': True, 'title': 'foobar', 'price': 0, 'currency': 'SEK', 'description': 'tintin'}]}, 500, 'UNHANDLED_SERVER_ERROR', "Announce native_picture_url is not set"],
        ]

        for data, status, error, msg in tests:
            j = self.assertPostReturnError(
                'v1/announces/process',
                data,
                status,
                error,
                auth="Bearer %s" % self.token
            )
            self.assertTrue(msg in j['error_description'])


    def test_v1_announces_process__no_announce(self):
        sources = [
            'FACEBOOK', 'BLOCKET', 'EBAY', 'TRADERA', 'LEBONCOIN',
            'CITYBOARD', 'SHPOCK', 'TEST'
        ]

        for source in sources:
            self.assertPostReturnOk(
                'v1/announces/process',
                {
                    'source': 'TEST',
                    'announces': []
                },
                auth='Bearer %s' % self.token,
            )


    def test_v1_announces_process__sold_announce(self):
        self.cleanup()
        url = self.native_test_url1
        self.assertEqual(get_item_by_native_url(url), None)

        # First, no announce exists - No item gets archived
        self.process_sold_announce(native_url=url)
        self.assertEqual(get_item_by_native_url(url), None)

        # Create that item
        j = self.create_item(native_url=url)
        self.assertEqual(j['is_sold'], False)
        self.assertTrue('date_sold' not in j)
        self.assertTrue('price_sold' not in j)
        self.assertIsInES(j['item_id'], real=False)

        # Now process that announce as sold, again
        self.process_sold_announce(native_url=url)
        jj = self.get_item(native_url=url)

        self.assertTrue(jj['date_sold'])
        j['is_sold'] = True
        j['date_sold'] = jj['date_sold']
        self.assertEqual(jj, j)

        self.assertIsNotInES(j['item_id'], real=False)


    def test_v1_announces_process__incomplete_announce__rejected(self):
        self.cleanup()
        url = self.native_test_url1

        # Announce with a title that fails first curation
        self.process_incomplete_announce(native_url=url, title='wont match anything')
        self.assertEqual(get_item_by_native_url(url), None)

        # Announce with a price that fails first curation
        self.process_incomplete_announce(native_url=url, title='louis vuitton', price=0)
        self.assertEqual(get_item_by_native_url(url), None)


    def test_v1_announces_process__incomplete_announce__accepted(self):
        # TODO: load one announce with only limited data that pass the curator. Check that it enters the scraper queue
        pass

    def test_v1_announces_process__complete_announce__rejected(self):
        # TODO: load one complete announce that does not pass the curator. Check that no item is created and it does not enter the scraper queue
        pass

    def test_v1_announces_process__complete_announce__accepted(self):
        # TODO: load one complete announce that pass the curator. Check that an item is created and it does not enter the scraper queue
        pass
