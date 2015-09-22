
from gringotts.tests import rest


class DownloadsTestCase(rest.RestfulTestCase):

    def setUp(self):
        super(DownloadsTestCase, self).setUp()

        self.download_path = '/v2/downloads'

    def test_download_charges_with_negative_limit_and_offset(self):
        path = "%s/%s" % (self.download_path, 'charges')
        self.check_invalid_limit_or_offset(path)

    def test_download_orders_with_negative_limit_and_offset(self):
        path = "%s/%s" % (self.download_path, 'orders')
        self.check_invalid_limit_or_offset(path)
