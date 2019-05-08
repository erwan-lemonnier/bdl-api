import logging
from pymacaron.test import PyMacaronTestCase
from bdl.utils import gen_jwt_token

log = logging.getLogger(__name__)


class BDLTests(PyMacaronTestCase):

    def setUp(self):
        super().setUp()
        self.token = gen_jwt_token(type='test')

        self.item_id1 = 'test-0000001'
        self.item_id2 = 'test-0000002'


    def tearDown(self):
        self.cleanup()
        super().tearDown()


    def cleanup(self):
        # TODO: delete the test items from the items and archiveditems tables
        pass


    def create_item(self, item_id=None, price=1000, currency='SEK', country='SE', price_is_fixed=False):
        if not item_id:
            item_id = self.item_id1
        j = self.assertPostReturnJson(
            'v1/item',
            {
                'index': 'BDL',
                'real': False,
                'source': 'TEST',
                'slug': '',
                'item_id': item_id,
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


    def assertIsItem(self, j):
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
