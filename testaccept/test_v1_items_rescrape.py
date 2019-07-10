import os
import imp
import logging


common = imp.load_source('common', os.path.join(os.path.dirname(__file__), 'common.py'))


log = logging.getLogger(__name__)


class Tests(common.BDLTests):

    def test_v1_items_rescrape__auth_required(self):
        self.assertPostReturnError(
            'v1/items/rescrape',
            {
                'index': 'BDL',
                'source': 'TRADERA',
                'percentage': 1,
            },
            401,
            'AUTHORIZATION_HEADER_MISSING',
        )


    def test_v1_items_rescrape__invalid_data(self):
        tests = [
            [{}, 400, 'INVALID_PARAMETER', "'index' is a required property"],
            [{'index': 'BOB'}, 400, 'INVALID_PARAMETER', "'BOB' is not one of"],
            [{'index': 'BDL'}, 400, 'INVALID_PARAMETER', "'source' is a required property"],
            [{'index': 'BDL', 'source': 'TRADERA'}, 400, 'INVALID_PARAMETER', "'percentage' is a required property"],
            [{'index': 'BDL', 'source': 'TRADERA', 'percentage': 'bob'}, 400, 'INVALID_PARAMETER', "'bob' is not of type 'integer'"],
            [{'index': 'BDL', 'source': 'TRADERA', 'percentage': 0}, 400, 'INVALID_PARAMETER', "percentage 0 is not between 1 and 100"],
            [{'index': 'BDL', 'source': 'TRADERA', 'percentage': 101}, 400, 'INVALID_PARAMETER', "percentage 101 is not between 1 and 100"],
        ]

        for data, status, error, msg in tests:
            j = self.assertPostReturnError(
                'v1/items/rescrape',
                data,
                status,
                error,
                auth="Bearer %s" % self.token
            )
            self.assertTrue(msg in j['error_description'])
