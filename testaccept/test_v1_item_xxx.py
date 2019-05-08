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
        self.create_item(item_id=self.item_id1)

        j = self.assertGetReturnJson(
            'v1/item/%s' % self.item_id1,
            auth="Bearer %s" % self.token,
        )

        self.assertEqual(j['date_created'], j['date_last_check'])
        self.assertEqual(
            j,
            {
                'count_views': 1,
                'country': 'SE',
                'currency': 'SEK',
                'date_created': j['date_created'],
                'date_last_check': j['date_last_check'],
                'description': 'This i a test description',
                'display_priority': 1,
                'index': 'BDL',
                'item_id': 'test-0000001',
                'native_url': 'bob',
                'picture_url': 'bob',
                'picture_url_w400': 'bob',
                'picture_url_w600': 'bob',
                'price': 1000.0,
                'price_is_fixed': False,
                'real': False,
                'searchable_string': '-',
                'slug': '-',
                'source': 'TEST',
                'tags': [],
                'title': 'This is a test title'
            },
        )

        # Get again and verify that count_view is increased
        jj = self.assertGetReturnJson(
            'v1/item/%s' % self.item_id1,
            auth="Bearer %s" % self.token,
        )
        j['count_views'] = 2
        self.assertEqual(jj, j)
