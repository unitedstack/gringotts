from gringotts.tests import fake_data
from gringotts.tests import db_fixtures
from gringotts.tests.api.v1 import FunctionalTest


class TestAccounts(FunctionalTest):
    PATH = '/accounts'

    def setUp(self):
        super(TestAccounts, self).setUp()
        self.useFixture(db_fixtures.DatabaseInit(self.conn))
        self.headers = {'X-Roles': 'admin'}

    def test_get_accounts(self):
        accounts = self.get_json(self.PATH, headers=self.headers)
        self.assertEqual(2, len(accounts))
        self.assertEqual('100.0000',accounts[0]['balance'])
        self.assertEqual('8975.0000',accounts[1]['balance'])

    def test_get_single_account(self):
        path = self.PATH + '/' + fake_data.DEMO_PROJECT_ID
        account = self.get_json(path, headers=self.headers)
        self.assertEqual('100.0000', account['balance'])
