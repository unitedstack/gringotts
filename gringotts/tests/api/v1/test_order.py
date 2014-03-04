from gringotts.tests import db_fixtures
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
        self.assertEqual(7, data['total_count'])

        # instance
        self.assertEqual('0.0900', data['orders'][6]['total_price'])
        self.assertEqual('0.0170', data['orders'][5]['total_price'])
        self.assertEqual('0.1053', data['orders'][4]['total_price'])
        self.assertEqual('0.0303', data['orders'][3]['total_price'])

        # volume
        self.assertEqual('0.0040', data['orders'][2]['total_price'])
        self.assertEqual('0.0047', data['orders'][1]['total_price'])

        # router
        self.assertEqual('0.0500', data['orders'][0]['total_price'])

    def test_get_orders_with_type(self):
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))
        data = self.get_json(self.PATH, headers=self.headers, type='instance')
        self.assertEqual(4, data['total_count'])

    def test_get_orders_with_time_range(self):
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))
        start_time = '2014-01-08T00:00:00'
        end_time = '2014-01-09T00:00:00'
        data = self.get_json(self.PATH, headers=self.headers,
                             start_time=start_time, end_time=end_time)
        self.assertEqual(3, data['total_count'])
        self.assertEqual('0.0900', data['orders'][2]['total_price'])
        self.assertEqual('0.0040', data['orders'][1]['total_price'])
        self.assertEqual('0.0500', data['orders'][0]['total_price'])

    def test_get_orders_with_pagination(self):
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))

        # First page
        data = self.get_json(self.PATH, headers=self.headers,
                             limit=3, offset=0)
        self.assertEqual(7, data['total_count'])
        self.assertEqual(3, len(data['orders']))

        # Third page
        data = self.get_json(self.PATH, headers=self.headers,
                             limit=3, offset=6)
        self.assertEqual(7, data['total_count'])
        self.assertEqual(1, len(data['orders']))

    def test_get_orders_summary(self):
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))
        path = self.PATH + '/summary'
        data = self.get_json(path, headers=self.headers)
        self.assertEqual(7, data['total_count'])
        self.assertEqual('0.3013', data['total_price'])

        self.assertEqual(4, data['summaries'][0]['total_count'])
        self.assertEqual('0.2426', data['summaries'][0]['total_price'])
        self.assertEqual('instance', data['summaries'][0]['order_type'])

    def test_get_orders_summary_with_time_range(self):
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))
        start_time = '2014-01-08T00:00:00'
        end_time = '2014-01-09T00:00:00'
        path = self.PATH + '/summary'
        data = self.get_json(path, headers=self.headers,
                             start_time=start_time, end_time=end_time)
        self.assertEqual(3, data['total_count'])
        self.assertEqual('0.1440', data['total_price'])
        self.assertEqual(1, data['summaries'][0]['total_count'])
        self.assertEqual('0.0900', data['summaries'][0]['total_price'])
        self.assertEqual('instance', data['summaries'][0]['order_type'])

    def test_get_single_order(self):
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))
        orders = self.get_json(self.PATH, headers=self.headers)

        # check vm3
        order_id = orders['orders'][4]['order_id']
        path = self.PATH + '/' + order_id
        data = self.get_json(path, headers=self.headers)

        self.assertEqual(3, len(data['bills']))

        # check last bill
        self.assertEqual('0.0900', data['bills'][0]['unit_price'])
        self.assertEqual('0.0900', data['bills'][0]['total_price'])

        # check bill time is sequential
        self.assertEqual('2014-03-08T03:38:36', data['bills'][2]['start_time'][:19])
        self.assertEqual('2014-03-08T03:48:36', data['bills'][2]['end_time'][:19])
        self.assertEqual('2014-03-08T03:48:36', data['bills'][1]['start_time'][:19])
        self.assertEqual('2014-03-08T03:58:36', data['bills'][1]['end_time'][:19])
        self.assertEqual('2014-03-08T03:58:36', data['bills'][0]['start_time'][:19])
        self.assertEqual('2014-03-08T04:58:36', data['bills'][0]['end_time'][:19])

    def test_get_single_order_with_time_range(self):
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))
        orders = self.get_json(self.PATH, headers=self.headers)

        # check vm4
        order_id = orders['orders'][3]['order_id']
        path = self.PATH + '/' + order_id
        start_time = '2014-04-08T00:00:00'
        end_time = '2014-04-08T03:50:00'
        data = self.get_json(path, headers=self.headers,
                             start_time=start_time, end_time=end_time)

        self.assertEqual(2, len(data['bills']))

        # check bill's timestamp
        self.assertEqual('2014-04-08T03:38:36', data['bills'][1]['start_time'][:19])
        self.assertEqual('2014-04-08T03:48:36', data['bills'][1]['end_time'][:19])
        self.assertEqual('2014-04-08T03:48:36', data['bills'][0]['start_time'][:19])
        self.assertEqual('2014-04-08T03:58:36', data['bills'][0]['end_time'][:19])

    def test_get_single_order_with_pagination(self):
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))
        orders = self.get_json(self.PATH, headers=self.headers)

        # check vm4
        order_id = orders['orders'][3]['order_id']
        path = self.PATH + '/' + order_id

        # first page
        data = self.get_json(path, headers=self.headers,
                             limit=2, offset=0)

        self.assertEqual(2, len(data['bills']))

        # second page
        data = self.get_json(path, headers=self.headers,
                             limit=2, offset=2)

        self.assertEqual(1, len(data['bills']))
