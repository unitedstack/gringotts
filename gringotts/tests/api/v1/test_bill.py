from gringotts.tests import db_fixtures
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

        self.assertEqual('0.3013', data['total_price'])
        self.assertEqual(13, len(data['bills']))

    def test_get_bills_with_type(self):
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))
        data = self.get_json(self.PATH, headers=self.headers, type='instance')

        self.assertEqual(9, len(data['bills']))

    def test_get_bills_with_time_range(self):
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))
        start_time = '2014-01-08T00:00:00'
        end_time = '2014-01-09T00:00:00'
        data = self.get_json(self.PATH, headers=self.headers,
                             start_time=start_time, end_time=end_time)

        self.assertEqual(3, len(data['bills']))
        self.assertEqual('0.1440', data['total_price'])

    def test_get_bills_with_pagination(self):
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))

        # first page
        data = self.get_json(self.PATH, headers=self.headers,
                             limit=5, offset=0)

        self.assertEqual(13, data['total_count'])
        self.assertEqual(5, len(data['bills']))

        # last page
        data = self.get_json(self.PATH, headers=self.headers,
                             limit=5, offset=10)

        self.assertEqual(13, data['total_count'])
        self.assertEqual(3, len(data['bills']))

        # null page
        data = self.get_json(self.PATH, headers=self.headers,
                             limit=5, offset=15)

        self.assertEqual(13, data['total_count'])
        self.assertEqual(0, len(data['bills']))

    def test_get_bill_trends(self):
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))
        path = '/bills/trends'
        data = self.get_json(path, headers=self.headers)

        self.assertEqual(12, len(data))
