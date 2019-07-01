import os
import imp
import logging


common = imp.load_source('common', os.path.join(os.path.dirname(__file__), 'common.py'))


log = logging.getLogger(__name__)


class Tests(common.BDLTests):

    def test_v1_search_latest__auth_required(self):
        self.assertGetReturnError(
            'v1/search/latest?source=bob',
            401,
            'AUTHORIZATION_HEADER_MISSING',
        )


    def test_v1_search_latest__invalid_data(self):
        tests = [
            ['', 400, 'INVALID_PARAMETER', "source is a required parameter"],
        ]

        for query, status, error, msg in tests:
            j = self.assertGetReturnError(
                'v1/search/latest?%s' % query,
                status,
                error,
                auth="Bearer %s" % self.token
            )
            self.assertTrue(msg in j['error_description'])


    def test_v1_search_latest__bdl__live(self):
        j = self.assertGetReturnJson(
            'v1/search/latest?source=TRADERA',
            auth="Bearer %s" % self.token,
        )
        self.assertIsItem(j)
        self.assertTrue(j['bdlitem']['epoch_published'])

        # Get item from non-existent source
        self.assertGetReturnError(
            'v1/search/latest?source=DOESNOTEXIST',
            404,
            'ES_ITEM_NOT_FOUND',
            auth="Bearer %s" % self.token,
        )
