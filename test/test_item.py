import os
import logging
from pymacaron_core.swagger.apipool import ApiPool
from bdl.model.item import model_to_item
from bdl.formats import get_custom_formats
from unittest import TestCase


log = logging.getLogger(__name__)


class Tests(TestCase):

    def setUp(self):
        ApiPool.add(
            'bdl',
            yaml_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'apis', 'bdl.yaml'),
            formats=get_custom_formats(),
        )
        self.maxDiff = None


    def test_generate_item_id(self):
        i = ApiPool.bdl.model.Item()
        model_to_item(i)

        i.source = 'TEST'
        self.assertEqual(i.item_id, None)
        i.generate_id()
        self.assertTrue(i.item_id.startswith('tst-'))
        self.assertEqual(len(i.item_id), 14)

        i.item_id = None
        i.source = 'BLOCKET'
        i.generate_id()
        self.assertTrue(i.item_id.startswith('bl-'))

        i.item_id = None
        i.source = 'TRADERA'
        i.generate_id()
        self.assertTrue(i.item_id.startswith('tr-'))

        # item_id is not regenerated if already set
        i.source = 'TEST'
        i.generate_id()
        self.assertFalse(i.item_id.startswith('tst-'))


    def test_set_slug(self):
        i = ApiPool.bdl.model.Item(item_id='tst-1234')
        model_to_item(i)

        tests = [
            ['"Orre" i stengods, Gunnar Nylund Rörtrand, 1900 talets andra hälft.', 1500, 'sek', 'Orre-i-stengods-Gunnar-Nylund-Rortrand-1900-talets-andra-halft_1500_sek__tst-1234'],
            ['a&b-c_d e!fGH.', 0, 'sek', 'a-b-c-d-e-fGH_0_sek__tst-1234'],
        ]

        for title, price, currency, slug in tests:
            i.title = title
            i.price = price
            i.currency = currency
            i.set_slug()
            self.assertEqual(i.slug, slug)
