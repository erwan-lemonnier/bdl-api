import os
import imp
import logging


common = imp.load_source('common', os.path.join(os.path.dirname(__file__), 'common.py'))


log = logging.getLogger(__name__)


class Tests(common.BDLTests):

    def test_v1_announces_process__auth_required(self):
        self.assertPostReturnError(
            'v1/announces/process',
            {'source': 'TEST', 'announces': []},
            401,
            'AUTHORIZATION_HEADER_MISSING',
        )


    def test_v1_announces_process__invalid_data(self):
        tests = [
            [{}, 400, 'INVALID_PARAMETER', "'source' is a required property"],
            [{'source': 'TEST'}, 400, 'INVALID_PARAMETER', "'announces' is a required property"],
        ]

        for data, status, error, msg in tests:
            j = self.assertPostReturnError(
                'v1/announces/process',
                data,
                status,
                error,
                auth="Bearer %s" % self.token
            )
            self.assertTrue(msg in j['error_description'])


    def test_v1_announces_process__no_announce(self):
        sources = [
            'FACEBOOK', 'BLOCKET', 'EBAY', 'TRADERA', 'LEBONCOIN',
            'CITYBOARD', 'SHPOCK', 'TEST'
        ]

        for source in sources:
            self.assertPostReturnOk(
                'v1/announces/process',
                {
                    'source': 'TEST',
                    'announces': []
                },
                auth='Bearer %s' % self.token,
            )


    def test_v1_announces_process__incomplete_announce__rejected(self):
        # TODO: load one announce with only limited data that does not pass the curator. Check that it does not enter the scraper queue
        pass

    def test_v1_announces_process__incomplete_announce__accepted(self):
        # TODO: load one announce with only limited data that pass the curator. Check that it enters the scraper queue
        pass

    def test_v1_announces_process__complete_announce__rejected(self):
        # TODO: load one complete announce that does not pass the curator. Check that no item is created and it does not enter the scraper queue
        pass

    def test_v1_announces_process__complete_announce__accepted(self):
        # TODO: load one complete announce that pass the curator. Check that an item is created and it does not enter the scraper queue
        pass
