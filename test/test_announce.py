import os
import logging
from pymacaron_core.swagger.apipool import ApiPool
from bdl.model.announce import model_to_announce
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


    def test_identify_language(self):
        a = ApiPool.bdl.model.Announce()
        model_to_announce(a)

        a.title = 'this is a title in english'
        a.identify_language()
        self.assertEqual(a.language, 'en')

        a.title = "et ca c'est en francais"
        a.identify_language()
        self.assertEqual(a.language, 'fr')

        a.description = 'lite svenska?'
        a.identify_language()
        self.assertEqual(a.language, 'fr')

        a.description = 'men om man skriver massor på svenska då blir det språket dominant'
        a.identify_language()
        self.assertEqual(a.language, 'no')  # lol

        a.title = 'så låt oss ha allt på svenska'
        a.identify_language()
        self.assertEqual(a.language, 'sv')
