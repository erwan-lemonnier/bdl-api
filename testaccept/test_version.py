import logging
import os
from pymacaron.test import PyMacaronTestCase


log = logging.getLogger(__name__)


class Test(PyMacaronTestCase):

    def setUp(self):
        super(Test, self).setUp()
        self.verify_ssl = True if 'klue.' in os.environ.get('PYM_SERVER_HOST', '') else False
        log.debug("TEST: verify_ssl=%s" % self.verify_ssl)

    def test_ping(self):
        self.assertHasPing()

    def test_version(self):
        self.assertHasVersion(verify_ssl=self.verify_ssl)

    def test_auth_version(self):
        self.assertHasAuthVersion(verify_ssl=self.verify_ssl)
