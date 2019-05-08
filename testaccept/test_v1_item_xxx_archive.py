import os
import imp
import logging


common = imp.load_source('common', os.path.join(os.path.dirname(__file__), 'common.py'))


log = logging.getLogger(__name__)


class Tests(common.BDLTests):

    def test_v1_item_xxx_archive__auth_required(self):
        self.assertPostReturnError(
            'v1/item/bob/archive',
            {'reason': 'SOLD'},
            401,
            'AUTHORIZATION_HEADER_MISSING',
        )


    def test_v1_item_xxx_archive__invalid_data(self):
        tests = [
            [{}, 400, 'INVALID_PARAMETER', "'reason' is a required property"],
            [{'reason': 'TEST'}, 400, 'INVALID_PARAMETER', "'TEST' is not one of"],
        ]

        for data, status, error, msg in tests:
            j = self.assertPostReturnError(
                'v1/item/bob/archive',
                data,
                status,
                error,
                auth="Bearer %s" % self.token
            )
            self.assertTrue(msg in j['error_description'])


    def test_v1_item_xxx_archive(self):
        self.cleanup()

        # Item is nowehere to be seen
        self.assertIsNotInItemTable(self.item_id1)
        self.assertIsNotInItemArchive(self.item_id1)
        self.assertIsNotInES(self.item_id1, real=False)

        self.create_item(item_id=self.item_id1)

        self.assertIsInItemTable(self.item_id1)
        self.assertIsNotInItemArchive(self.item_id1)
        self.assertIsInES(self.item_id1, real=False)

        # Now archive that item and check that we can still retrieve it
        j = self.assertPostReturnJson(
            'v1/item/%s/archive' % self.item_id1,
            {
                'reason': 'SOLD',
            },
            auth="Bearer %s" % self.token,
        )
        self.assertIsItem(j, is_sold=True)

        self.assertIsNotInItemTable(self.item_id1)
        self.assertIsInItemArchive(self.item_id1)
        self.assertIsNotInES(self.item_id1, real=False)

        # We can still get it
        jj = self.assertGetReturnJson(
            'v1/item/%s' % self.item_id1,
            auth="Bearer %s" % self.token,
        )
        self.assertIsItem(jj, is_sold=True)

        j['count_views'] = j['count_views'] + 1
        self.assertEqual(jj, j)
