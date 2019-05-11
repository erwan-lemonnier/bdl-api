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


    def test__str__(self):
        i = ApiPool.bdl.model.Item(
            item_id='tst-1234',
            bdlitem=ApiPool.bdl.model.BDLItem(),
        )
        model_to_item(i)

        self.assertEqual(str(i), "<Item tst-1234: <BDLItem>>")
        i.bdlitem.title = 'short title'
        self.assertEqual(str(i), "<Item tst-1234: <BDLItem 'short title'>>")
        i.bdlitem.title = 'And a very long title that is more than 20 characters long'
        self.assertEqual(str(i), "<Item tst-1234: <BDLItem 'And a very long titl..'>>")
        i.bdlitem.price = 12
        i.bdlitem.currency = 'SEK'
        self.assertEqual(str(i), "<Item tst-1234: <BDLItem 'And a very long titl..' 12 SEK>>")


    def test_set_item_id(self):
        i = ApiPool.bdl.model.Item()
        model_to_item(i)

        i.source = 'TEST'
        self.assertEqual(i.item_id, None)
        i.set_item_id()
        self.assertTrue(i.item_id.startswith('tst-'))
        self.assertEqual(len(i.item_id), 14)

        i.item_id = None
        i.source = 'BLOCKET'
        i.set_item_id()
        self.assertTrue(i.item_id.startswith('bl-'))

        i.item_id = None
        i.source = 'TRADERA'
        i.set_item_id()
        self.assertTrue(i.item_id.startswith('tr-'))

        # item_id is not regenerated if already set
        i.source = 'TEST'
        i.set_item_id()
        self.assertFalse(i.item_id.startswith('tst-'))
