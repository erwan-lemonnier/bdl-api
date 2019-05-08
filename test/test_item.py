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
        item = ApiPool.bdl.model.Item(index='BDL')
        model_to_item(item)
        self.assertEqual(item.item_id, None)
        item.generate_id()
        self.assertTrue(item.item_id.startswith('bdl-'))
        self.assertEqual(len(item.item_id), 34)
