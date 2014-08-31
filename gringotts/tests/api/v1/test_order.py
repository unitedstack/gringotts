import datetime

from gringotts.tests import db_fixtures
from gringotts.tests import fake_data
from gringotts.tests.api.v1 import FunctionalTest


class TestOrders(FunctionalTest):
    PATH = '/orders'

    def setUp(self):
        super(TestOrders, self).setUp()
        self.useFixture(db_fixtures.DatabaseInit(self.conn))
        self.headers = {'X-Roles': 'admin'}

    def test_get_orders_none(self):
        data = self.get_json(self.PATH, headers=self.headers)
        self.assertEqual(0, data['total_count'])
        self.assertEqual(0, len(data['orders']))

    def test_get_orders(self):
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))
        data = self.get_json(self.PATH, headers=self.headers)
        self.assertEqual(8, data['total_count'])

        # instance
        self.assertEqual('0.0900', data['orders'][7]['total_price'])
        self.assertEqual('0.0150', data['orders'][6]['total_price'])
        self.assertEqual('0.1050', data['orders'][5]['total_price'])
        self.assertEqual('0.0450', data['orders'][4]['total_price'])
        self.assertEqual('0.1860', data['orders'][3]['total_price'])

        # volume
        self.assertEqual('0.0040', data['orders'][2]['total_price'])
        self.assertEqual('0.0060', data['orders'][1]['total_price'])

        # router
        self.assertEqual('0.0500', data['orders'][0]['total_price'])

    def test_get_orders_with_type(self):
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))
        data = self.get_json(self.PATH, headers=self.headers, type='instance')
        self.assertEqual(5, data['total_count'])

    def test_get_orders_with_time_range(self):
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))
        start_time = fake_data.instance_created_time - datetime.timedelta(minutes=5)
        end_time = fake_data.instance_stopped_time + datetime.timedelta(minutes=5)
        data = self.get_json(self.PATH, headers=self.headers,
                             start_time=start_time, end_time=end_time)
        self.assertEqual(5, data['total_count'])
        self.assertEqual('0.0900', data['orders'][4]['total_price'])
        self.assertEqual('0.0150', data['orders'][3]['total_price'])
        self.assertEqual('0.0150', data['orders'][2]['total_price'])
        self.assertEqual('0.0150', data['orders'][1]['total_price'])
        self.assertEqual('0.0450', data['orders'][0]['total_price'])

    def test_get_orders_with_pagination(self):
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))

        # First page
        data = self.get_json(self.PATH, headers=self.headers,
                             limit=3, offset=0)
        self.assertEqual(8, data['total_count'])
        self.assertEqual(3, len(data['orders']))

        # Third page
        data = self.get_json(self.PATH, headers=self.headers,
                             limit=3, offset=6)
        self.assertEqual(8, data['total_count'])
        self.assertEqual(2, len(data['orders']))

    def test_get_orders_summary(self):
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))
        path = self.PATH + '/summary'
        data = self.get_json(path, headers=self.headers)
        self.assertEqual(8, data['total_count'])
        self.assertEqual('0.5010', data['total_price'])

        self.assertEqual(5, data['summaries'][0]['total_count'])
        self.assertEqual('0.4410', data['summaries'][0]['total_price'])
        self.assertEqual('instance', data['summaries'][0]['order_type'])

    def test_get_orders_summary_with_time_range(self):
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))
        start_time = fake_data.instance_created_time - datetime.timedelta(minutes=5)
        end_time = fake_data.instance_stopped_time + datetime.timedelta(minutes=5)
        path = self.PATH + '/summary'
        data = self.get_json(path, headers=self.headers,
                             start_time=start_time, end_time=end_time)
        self.assertEqual(5, data['total_count'])
        self.assertEqual('0.1800', data['total_price'])
        self.assertEqual(5, data['summaries'][0]['total_count'])
        self.assertEqual('0.1800', data['summaries'][0]['total_price'])
        self.assertEqual('instance', data['summaries'][0]['order_type'])

    def test_get_single_order(self):
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))
        orders = self.get_json(self.PATH, headers=self.headers)

        # check vm3
        order_id = orders['orders'][5]['order_id']
        path = self.PATH + '/' + order_id
        data = self.get_json(path, headers=self.headers)

        self.assertEqual(3, len(data['bills']))

        # check last bill
        self.assertEqual('0.0900', data['bills'][0]['unit_price'])
        self.assertEqual('0.0900', data['bills'][0]['total_price'])

        # check bill time is sequential
        bill_2_start_time = fake_data.instance_created_time.isoformat()[:19]
        bill_2_end_time = fake_data.instance_stopped_time.isoformat()[:19]
        bill_1_start_time = fake_data.instance_stopped_time.isoformat()[:19]
        bill_1_end_time = fake_data.instance_started_time.isoformat()[:19]
        bill_0_start_time = fake_data.instance_started_time.isoformat()[:19]
        bill_0_end_time = (fake_data.instance_started_time + datetime.timedelta(hours=1)).isoformat()[:19]

        self.assertEqual(bill_2_start_time, data['bills'][2]['start_time'][:19])
        self.assertEqual(bill_2_end_time, data['bills'][2]['end_time'][:19])
        self.assertEqual(bill_1_start_time, data['bills'][1]['start_time'][:19])
        self.assertEqual(bill_1_end_time, data['bills'][1]['end_time'][:19])
        self.assertEqual(bill_0_start_time, data['bills'][0]['start_time'][:19])
        self.assertEqual(bill_0_end_time, data['bills'][0]['end_time'][:19])

    def test_get_single_order_with_time_range(self):
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))
        orders = self.get_json(self.PATH, headers=self.headers)

        # check vm4
        order_id = orders['orders'][4]['order_id']
        path = self.PATH + '/' + order_id
        start_time = fake_data.instance_created_time - datetime.timedelta(minutes=5)
        end_time = fake_data.instance_stopped_time + datetime.timedelta(minutes=5)
        data = self.get_json(path, headers=self.headers,
                             start_time=start_time, end_time=end_time)

        self.assertEqual(2, len(data['bills']))

        # check bill's timestamp
        bill_1_start_time = fake_data.instance_created_time.isoformat()[:19]
        bill_1_end_time = fake_data.instance_stopped_time.isoformat()[:19]
        bill_0_start_time = fake_data.instance_stopped_time.isoformat()[:19]
        bill_0_end_time = fake_data.instance_started_time.isoformat()[:19]

        self.assertEqual(bill_1_start_time, data['bills'][1]['start_time'][:19])
        self.assertEqual(bill_1_end_time, data['bills'][1]['end_time'][:19])
        self.assertEqual(bill_0_start_time, data['bills'][0]['start_time'][:19])
        self.assertEqual(bill_0_end_time, data['bills'][0]['end_time'][:19])

    def test_get_single_order_with_pagination(self):
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))
        orders = self.get_json(self.PATH, headers=self.headers)

        # check vm4
        order_id = orders['orders'][4]['order_id']
        path = self.PATH + '/' + order_id

        # first page
        data = self.get_json(path, headers=self.headers,
                             limit=2, offset=0)

        self.assertEqual(2, len(data['bills']))

        # second page
        data = self.get_json(path, headers=self.headers,
                             limit=2, offset=2)

        self.assertEqual(2, len(data['bills']))

    def test_post_order(self):
        new_order = {
            "order_id": "fake_order_id",
            "unit_price": "0.056",
            "unit": "hour",
            "resource_id": "fake_resource_id",
            "resource_name": "fake_resource_name",
            "user_id": fake_data.DEMO_USER_ID,
            "project_id": fake_data.DEMO_PROJECT_ID,
            "region_id": "fake_region_id",
            "type": "instance",
            "status": "running"
        }
        self.post_json(self.PATH, new_order, headers=self.headers)

        data = self.get_json(self.PATH, headers=self.headers)
        self.assertEqual(1, data['total_count'])
        self.assertEqual(fake_data.ADMIN_USER_ID, data['orders'][0]['user_id'])
        self.assertEqual(fake_data.DOMAIN_ID, data['orders'][0]['domain_id'])

    def test_put_order(self):
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))

        # test vm2
        orders = self.get_json(self.PATH, headers=self.headers)
        self.assertEqual('0.0000', orders['orders'][6]['unit_price'])
        self.assertEqual('stopped', orders['orders'][6]['status'])

        order_id = orders['orders'][6]['order_id']

        body = {
            "order_id": order_id,
            "change_to": "running",
            "cron_time": None,
            "change_order_status": True,
            "first_change_to": None
        }

        self.put_json(self.PATH, body, headers=self.headers)

        orders = self.get_json(self.PATH, headers=self.headers)
        self.assertEqual('0.0900', orders['orders'][6]['unit_price'])
        self.assertEqual('running', orders['orders'][6]['status'])
