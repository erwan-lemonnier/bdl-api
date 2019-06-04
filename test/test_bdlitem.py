import os
import logging
from uuid import uuid4
from boto.s3.key import Key
from pymacaron_core.swagger.apipool import ApiPool
from bdl.model.bdlitem import model_to_bdlitem
from bdl.formats import get_custom_formats
from bdl.io.s3 import get_s3_conn
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


    def test_import_pictures(self):
        i = ApiPool.bdl.model.BDLItem()
        model_to_bdlitem(i)

        i.item_id = 'test-%s' % str(uuid4()).replace('-', '')[0:10]
        i.native_picture_url = 'https://img.bazardelux.com/cat2.jpg'

        i.import_pictures()

        self.assertEqual(i.picture_url, 'https://img.bazardelux.com/%s.jpg' % i.item_id)
        self.assertEqual(i.picture_url_w200, 'https://img.bazardelux.com/%s_w200.jpg' % i.item_id)
        self.assertEqual(i.picture_url_w400, 'https://img.bazardelux.com/%s_w400.jpg' % i.item_id)
        self.assertEqual(i.picture_url_w600, 'https://img.bazardelux.com/%s_w600.jpg' % i.item_id)

        # Cleanup
        bucket = get_s3_conn().get_bucket('bdl-pictures')

        def delete_key(name):
            k = Key(bucket)
            k.key = name
            bucket.delete_key(k)

        delete_key('%s.jpg' % i.item_id)
        delete_key('%s_w200.jpg' % i.item_id)
        delete_key('%s_w400.jpg' % i.item_id)
        delete_key('%s_w600.jpg' % i.item_id)
