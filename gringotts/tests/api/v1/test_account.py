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

        # Default is desc
        self.assertEqual('100.0000',accounts[1]['balance'])
        self.assertEqual('8975.0000',accounts[0]['balance'])

    def test_get_single_account(self):
        path = self.PATH + '/' + fake_data.DEMO_PROJECT_ID
        account = self.get_json(path, headers=self.headers)
        self.assertEqual('100.0000', account['balance'])

    def test_charge_account(self):
        path = self.PATH + '/' + fake_data.DEMO_PROJECT_ID
        data = {'value': 100}

        self.put_json(path, data, headers=self.headers)

        account = self.get_json(path, headers=self.headers)
        self.assertEqual('200.0000', account['balance'])

    def test_charge_negative_account(self):
        path = self.PATH + '/' + fake_data.DEMO_PROJECT_ID
        data = {'value': -100}

        resp = self.put_json(path, data, expect_errors=True,
                             headers=self.headers)
        self.assertEqual(400, resp.status_int)

    def test_get_account_charges(self):
        charge_path = self.PATH + '/' + fake_data.DEMO_PROJECT_ID
        data = {'value': 100}

        self.put_json(charge_path, data, headers=self.headers)
        self.put_json(charge_path, data, headers=self.headers)
        self.put_json(charge_path, data, headers=self.headers)

        path = self.PATH + '/' + fake_data.DEMO_PROJECT_ID + '/charges'
        charges = self.get_json(path, headers=self.headers)

        self.assertEqual(3, len(charges['charges']))
        self.assertEqual('300.0000', charges['total_price'])
        self.assertEqual(3, charges['total_count'])
