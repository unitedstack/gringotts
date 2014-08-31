import datetime

from gringotts.tests import db_fixtures
from gringotts.tests import fake_data
from gringotts.tests.api.v1 import FunctionalTest


class TestBills(FunctionalTest):
    PATH = '/bills/detail'

    def setUp(self):
        super(TestBills, self).setUp()
        self.useFixture(db_fixtures.DatabaseInit(self.conn))
        self.headers = {'X-Roles': 'admin'}

    def test_get_bills_none(self):
        data = self.get_json(self.PATH, headers=self.headers)
        self.assertEqual('0.0000', data['total_price'])
        self.assertEqual(0, len(data['bills']))

    def test_get_bills(self):
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))
        data = self.get_json(self.PATH, headers=self.headers)

        self.assertEqual('0.5010', data['total_price'])
        self.assertEqual(16, len(data['bills']))

    def test_get_bills_with_type(self):
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))
        data = self.get_json(self.PATH, headers=self.headers, type='instance')

        self.assertEqual(12, len(data['bills']))

    def test_get_bills_with_time_range(self):
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))
        start_time = fake_data.instance_created_time - datetime.timedelta(minutes=5)
        end_time = fake_data.instance_stopped_time + datetime.timedelta(minutes=5)
        data = self.get_json(self.PATH, headers=self.headers,
                             start_time=start_time, end_time=end_time)

        self.assertEqual(8, len(data['bills']))
        self.assertEqual('0.1800', data['total_price'])

    def test_get_bills_with_pagination(self):
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))

        # first page
        data = self.get_json(self.PATH, headers=self.headers,
                             limit=5, offset=0)

        self.assertEqual(16, data['total_count'])
        self.assertEqual(5, len(data['bills']))

        # last page
        data = self.get_json(self.PATH, headers=self.headers,
                             limit=5, offset=15)

        self.assertEqual(16, data['total_count'])
        self.assertEqual(1, len(data['bills']))

        # null page
        data = self.get_json(self.PATH, headers=self.headers,
                             limit=5, offset=20)

        self.assertEqual(16, data['total_count'])
        self.assertEqual(0, len(data['bills']))

    def test_get_bill_trends(self):
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))
        path = '/bills/trends'
        data = self.get_json(path, headers=self.headers)

        self.assertEqual(12, len(data))

    def test_post_bill(self):
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))
        orders = self.get_json('/orders', headers=self.headers)

        # add a hourly bill to vm1
        order_id = orders['orders'][7]['order_id']

        new_bill = {
            "order_id": order_id,
            "remarks": "Hourly Billing"
        }

        self.post_json('/bills', new_bill, headers=self.headers)

        path = '/orders/' + order_id
        data = self.get_json(path, headers=self.headers)

        self.assertEqual(2, len(data['bills']))

    def test_put_bill(self):
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))
        orders = self.get_json('/orders', headers=self.headers)

        # colse the bill of vm1
        order_id = orders['orders'][7]['order_id']

        body = {
            "order_id": order_id,
            "action_time": fake_data.INSTANCE_1_STOPPED_TIME
        }

        self.put_json('/bills', body, headers=self.headers)

        path = '/orders/' + order_id
        data = self.get_json(path, headers=self.headers)

        self.assertEqual(1, len(data['bills']))
        self.assertEqual('0.0150', data['bills'][0]['total_price'])

        orders = self.get_json('/orders', headers=self.headers)
        self.assertEqual('changing', orders['orders'][7]['status'])
