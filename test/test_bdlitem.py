import os
import logging
from pymacaron_core.swagger.apipool import ApiPool
from bdl.model.bdlitem import model_to_bdlitem
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


    def test_get_slug(self):
        i = ApiPool.bdl.model.BDLItem()
        model_to_bdlitem(i)

        tests = [
            ['"Orre" i stengods, Gunnar Nylund Rörtrand, 1900 talets andra hälft.', 1500, 'sek', 'Orre-i-stengods-Gunnar-Nylund-Rortrand-1900-talets-andra-halft_1500_sek__tst-1234'],
            ['a&b-c_d e!fGH.', 0, 'sek', 'a-b-c-d-e-fGH_0_sek__tst-1234'],
        ]

        for title, price, currency, slug in tests:
            i.title = title
            i.price = price
            i.currency = currency
            s = i.get_slug(item_id='tst-1234')
            self.assertEqual(s, slug)
