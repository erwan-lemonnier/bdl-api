import os
import imp
import logging


common = imp.load_source('common', os.path.join(os.path.dirname(__file__), 'common.py'))


log = logging.getLogger(__name__)


class Tests(common.BDLTests):

    def test_v1_item_xxx__auth_required(self):
        self.assertGetReturnError(
            'v1/item/bob',
            401,
            'AUTHORIZATION_HEADER_MISSING',
        )


    def test_v1_item_xxx(self):
        self.cleanup()
        self.create_item(item_id=self.item_id1)

        j0 = self.assertGetReturnJson(
            'v1/item/%s' % self.item_id1,
            auth="Bearer %s" % self.token,
        )
        self.assertIsItem(j0)

        self.assertEqual(j0['date_created'], j0['date_last_check'])
        self.assertEqual(
            j0,
            {
                'count_views': 1,
                'country': 'SE',
                'currency': 'SEK',
                'date_created': j0['date_created'],
                'date_last_check': j0['date_last_check'],
                'description': 'This i a test description',
                'display_priority': 1,
                'index': 'BDL',
                'language': 'en',
                'is_sold': False,
                'item_id': 'test-0000001',
                'native_url': 'bob',
                'picture_url': 'bob',
                'picture_url_w400': 'bob',
                'picture_url_w600': 'bob',
                'price': 1000.0,
                'price_is_fixed': False,
                'real': False,
                'searchable_string': 'this is a test title this i a test description SOURCE_TEST COUNTRY_SE CURRENCY_SEK test-0000001',
                'slug': '-',
                'source': 'TEST',
                'tags': [],
                'title': 'This is a test title'
            },
        )

        # Get again and verify that count_view is increased
        j1 = self.assertGetReturnJson(
            'v1/item/%s' % self.item_id1,
            auth="Bearer %s" % self.token,
        )
        self.assertIsItem(j1)

        j0['count_views'] = 2
        self.assertEqual(j1, j0)

        # Now archive that item and check that we can still retrieve it
        j2 = self.assertPostReturnJson(
            'v1/item/%s/archive' % self.item_id1,
            {
                'reason': 'SOLD',
            },
            auth="Bearer %s" % self.token,
        )
        self.assertIsItem(j2, is_sold=True)
        j0['is_sold'] = True
        j0['date_sold'] = j2['date_sold']
        self.assertEqual(j2, j0)

        # We can still get it
        j3 = self.assertGetReturnJson(
            'v1/item/%s' % self.item_id1,
            auth="Bearer %s" % self.token,
        )
        self.assertIsItem(j3, is_sold=True)

        j0['count_views'] = 3
        self.assertEqual(j3, j0)
