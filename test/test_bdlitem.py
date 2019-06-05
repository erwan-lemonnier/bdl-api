import os
import imp
import logging
from uuid import uuid4
from pymacaron_core.swagger.apipool import ApiPool
from bdl.model.bdlitem import model_to_bdlitem
from bdl.formats import get_custom_formats
from unittest import TestCase


common = imp.load_source('common', os.path.join(os.path.dirname(__file__), '..', 'testaccept', 'common.py'))


log = logging.getLogger(__name__)


class Tests(TestCase):

    def setUp(self):
        ApiPool.add(
            'api',
            yaml_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'apis', 'api.yaml'),
            formats=get_custom_formats(),
        )
        self.maxDiff = None


    def test_get_slug(self):
        i = ApiPool.api.model.BDLItem()
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


    def test_import_pictures(self):
        i = ApiPool.api.model.BDLItem()
        model_to_bdlitem(i)

        item_id = 'test-%s' % str(uuid4()).replace('-', '')[0:10]
        i.native_picture_url = 'https://img.bazardelux.com/cat2.jpg'

        i.import_pictures(item_id)

        self.assertEqual(i.picture_url, 'https://img.bazardelux.com/%s.jpg' % item_id)
        self.assertEqual(i.picture_url_w200, 'https://img.bazardelux.com/%s_w200.jpg' % item_id)
        self.assertEqual(i.picture_url_w400, 'https://img.bazardelux.com/%s_w400.jpg' % item_id)
        self.assertEqual(i.picture_url_w600, 'https://img.bazardelux.com/%s_w600.jpg' % item_id)

        common.BDLTests().cleanup_pictures(item_id)
