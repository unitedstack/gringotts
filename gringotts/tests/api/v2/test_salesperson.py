
from gringotts.tests import rest


class SalespersonsTestCase(rest.RestfulTestCase):

    def setUp(self):
        super(SalespersonsTestCase, self).setUp()

        self.salesperson_path = '/v2/salespersons'

    def test_get_salesperson_accounts_with_negative_limit_or_offset(self):
        sales_id = self.new_user_id()
        path = "%s/%s/%s" % (self.salesperson_path, sales_id, 'accounts')
        self.check_invalid_limit_or_offset(path)
