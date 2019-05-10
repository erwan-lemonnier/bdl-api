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
        j = self.create_item(native_url=self.native_test_url1)
        item_id = j['item_id']
        self.assertTrue(item_id.startswith('tst-'))

        j0 = self.assertGetReturnJson(
            'v1/item/%s' % item_id,
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
                'description': 'A nice louis vuitton bag',
                'display_priority': 1,
                'index': 'BDL',
                'language': 'en',
                'is_sold': False,
                'item_id': item_id,
                'native_url': 'https://bdl.com/test1',
                'native_picture_url': 'bob',
                'picture_url': 'bob',
                'picture_url_w400': 'bob',
                'picture_url_w600': 'bob',
                'price': 1000.0,
                'price_is_fixed': False,
                'real': False,
                'searchable_string': 'this is a test title a nice louis vuitton bag SOURCE_TEST COUNTRY_SE CURRENCY_SEK %s :MODE: :BAGS: :FASHION: :LOUIS VUITTON: :LOUISVUITTON: :PATH:FASHION: :PATH:FASHION:BAGS: :PATH:FASHION:BAGS:LOUISVUITTON:' % item_id,
                'slug': 'This-is-a-test-title_1000_SEK__%s' % item_id,
                'source': 'TEST',
                'tags': [
                    'MODE',
                    'bags',
                    'fashion',
                    'louis vuitton',
                    'louisvuitton',
                    'path:fashion',
                    'path:fashion:bags',
                    'path:fashion:bags:louisvuitton'
                ],
                'picture_tags': [],
                'title': 'This is a test title'
            },
        )

        # Get again and verify that count_view is increased
        j1 = self.assertGetReturnJson(
            'v1/item/%s' % item_id,
            auth="Bearer %s" % self.token,
        )
        self.assertIsItem(j1)

        j0['count_views'] = 2
        self.assertEqual(j1, j0)

        # Now archive that item and check that we can still retrieve it
        j2 = self.assertPostReturnJson(
            'v1/item/%s/archive' % item_id,
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
            'v1/item/%s' % item_id,
            auth="Bearer %s" % self.token,
        )
        self.assertIsItem(j3, is_sold=True)

        j0['count_views'] = 3
        self.assertEqual(j3, j0)
