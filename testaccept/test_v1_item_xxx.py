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


    def test_v1_item_xxx__bdl(self):
        self.cleanup()
        j = self.create_bdl_item(native_url=self.native_test_url1)
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
                'date_created': j0['date_created'],
                'date_last_check': j0['date_last_check'],
                'display_priority': 1,
                'index': 'BDL',
                'item_id': item_id,
                'native_url': 'https://bdl.com/test1',
                'real': False,
                'searchable_string': 'this is a test title a nice louis vuitton bag SOURCE_TEST COUNTRY_SE CURRENCY_SEK %s :MODE: :BAGS: :FASHION: :LOUIS VUITTON: :LOUISVUITTON: :PATH:FASHION: :PATH:FASHION:BAGS: :PATH:FASHION:BAGS:LOUISVUITTON:' % item_id,
                'slug': 'This-is-a-test-title_1000_SEK__%s' % item_id,
                'source': 'TEST',
                'bdlitem': {
                    'country': 'SE',
                    'currency': 'SEK',
                    'description': 'A nice louis vuitton bag',
                    'language': 'en',
                    'has_ended': False,
                    'native_picture_url': 'https://img.bazardelux.com/cat2.jpg',
                    'picture_url': 'https://img.bazardelux.com/%s.jpg' % item_id,
                    'picture_url_w200': 'https://img.bazardelux.com/%s_w200.jpg' % item_id,
                    'picture_url_w400': 'https://img.bazardelux.com/%s_w400.jpg' % item_id,
                    'picture_url_w600': 'https://img.bazardelux.com/%s_w600.jpg' % item_id,
                    'price': 1000.0,
                    'price_is_fixed': False,
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
                'is_sold': True,
            },
            auth="Bearer %s" % self.token,
        )
        self.assertIsItem(j2, has_ended=True)
        j0['bdlitem']['has_ended'] = True
        j0['bdlitem']['is_sold'] = True
        j0['bdlitem']['date_sold'] = j2['bdlitem']['date_ended']
        j0['bdlitem']['date_ended'] = j2['bdlitem']['date_ended']
        self.assertEqual(j2, j0)

        # We can still get it
        j3 = self.assertGetReturnJson(
            'v1/item/%s' % item_id,
            auth="Bearer %s" % self.token,
        )
        self.assertIsItem(j3, has_ended=True)

        j0['count_views'] = 3
        self.assertEqual(j3, j0)

        self.cleanup_pictures(item_id)
