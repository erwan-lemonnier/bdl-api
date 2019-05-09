import os
import logging
from pymacaron_core.swagger.apipool import ApiPool
from bdl.model.announce import model_to_announce
from bdl.formats import get_custom_formats
from bdl.categories import PriceRange
from bdl.utils import html_to_unicode
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


    def test_has_ok_price(self):
        a = ApiPool.bdl.model.Announce()
        model_to_announce(a)

        tests = [
            ['SEK', 100, False],
            ['SEK', 400, True],
            ['SEK', 5000, True],
            ['SEK', 0, False],
            ['SEK', 99999999, False],
            ['SEK', 123456, False],
            ['EUR', 30, False],
            ['EUR', 5000, True],
            ['EUR', 0, False],
            ['EUR', 10001, False],
        ]

        for currency, price, want in tests:
            a.currency = currency
            a.price = price
            self.assertEqual(a.has_ok_price(), want)

        # Now, setting the price range
        tests = [
            ['SEK', 0, True],
            ['SEK', 1000001, True],
            ['SEK', 1000002, False],
        ]

        pr = PriceRange('sek', 0, 1000001)
        for currency, price, want in tests:
            a.currency = currency
            a.price = price
            self.assertEqual(a.has_ok_price(price_ranges=[pr]), want)


    def test_seems_sold(self):
        a = ApiPool.bdl.model.Announce()
        model_to_announce(a)

        tests = [
            ['sv', html_to_unicode('bordet är s&aring;ld'), True],
            ['en', 'bordet är såld', False],
            ['sv', 'bordet verkar i bra skick', False],
            ['en', 'bordet verkar i bra skick', False],
            ['en', 'table is sold', True],
            ['sv', 'table is sold', False],
        ]

        for language, title, want in tests:
            log.debug("Testing with [%s] [%s]" % (language, title))
            a.language = language
            a.title = title
            self.assertEqual(a.seems_sold(), want, "[%s]/[%s] seems_sold should be %s" % (language, title, want))
