import os
import imp
import logging


common = imp.load_source('common', os.path.join(os.path.dirname(__file__), 'common.py'))


log = logging.getLogger(__name__)


class Tests(common.BDLTests):

    def test_v1_search__auth_required(self):
        self.assertGetReturnError(
            'v1/search',
            401,
            'AUTHORIZATION_HEADER_MISSING',
        )


    def test_v1_search__bdl__live(self):
        j = self.assertGetReturnJson(
            'v1/search',
            auth="Bearer %s" % self.token,
        )

        self.assertTrue(j['count_found'] > 10)

        self.assertEqual(
            j,
            {
                "count_found": j['count_found'],
                "items": j['items'],
                "location": "ALL",
                "url_this": "/v1/search?page=0&page_size=50&location=ALL",
                "url_next": "/v1/search?page=1&page_size=50&location=ALL",
            }
        )

        for i in j['items']:
            self.assertIsItem(i, index='BDL')
        # TODO: check order of returned items


    def test_v1_search__bdl__live__pagination(self):
        j = self.assertGetReturnJson(
            'v1/search?page=1&page_size=10',
            auth="Bearer %s" % self.token,
        )

        self.assertEqual(len(j['items']), 10)
        self.assertTrue(j['count_found'] > 20)

        self.assertEqual(
            j,
            {
                "count_found": j['count_found'],
                "items": j['items'],
                "location": "ALL",
                "url_this": "/v1/search?page=1&page_size=10&location=ALL",
                "url_next": "/v1/search?page=2&page_size=10&location=ALL",
            }
        )


    def test_v1_search__bdl__live__no_hits(self):
        j = self.assertGetReturnJson(
            'v1/search?query=abracadabrerabradabra',
            auth="Bearer %s" % self.token,
        )

        self.assertEqual(
            j,
            {
                "count_found": 0,
                "items": [],
                "location": "ALL",
                "query": "abracadabrerabradabra",
                "url_this": "/v1/search?page=0&page_size=50&query=abracadabrerabradabra&location=ALL"
            }
        )
