import datetime

from gringotts.tests import db_fixtures
from gringotts.tests import fake_data
from gringotts.tests.api.v1 import FunctionalTest


class TestPrecharge(FunctionalTest):
    PATH = '/precharge'

    def setUp(self):
        super(TestPrecharge, self).setUp()
        self.useFixture(db_fixtures.DatabaseInit(self.conn))
        self.headers = {'X-Roles': 'admin'}

    def test_get_precharge_none(self):
        data = self.get_json(self.PATH, headers=self.headers)
        self.assertEqual(0, len(data))

    def test_get_precharge(self):
        self.useFixture(db_fixtures.PrechargeInit(self.conn))
        data = self.get_json(self.PATH, headers=self.headers)
        self.assertEqual(10, len(data))

    def test_get_precharge_by_code(self):
        self.useFixture(db_fixtures.PrechargeInit(self.conn))
        data = self.get_json(self.PATH, headers=self.headers)
        path = self.PATH + '/' + data[0]['code']
        precharge = self.get_json(path, headers=self.headers)
        self.assertEqual(data[0]['code'], precharge['code'])

    def test_post_precharge(self):
        body = {
            "number": 5,
            "price": "100"
        }
        self.post_json(self.PATH, body, headers=self.headers)

        data = self.get_json(self.PATH, headers=self.headers)
        self.assertEqual(5, len(data))

    def test_dispatch_precharge(self):
        self.useFixture(db_fixtures.PrechargeInit(self.conn))
        data = self.get_json(self.PATH, headers=self.headers)

        path = self.PATH + '/' + data[0]['code'] + '/dispatched'
        body = {"remarks": "guangyu@unitedstack.com"}

        self.put_json(path, body, headers=self.headers)

        path = self.PATH + '/' + data[0]['code']
        precharge = self.get_json(path, headers=self.headers)
        self.assertEqual(data[0]['code'], precharge['code'])
        self.assertEqual(True, precharge['dispatched'])
        self.assertEqual('guangyu@unitedstack.com', precharge['remarks'])

    def test_use_precharge(self):
        self.useFixture(db_fixtures.PrechargeInit(self.conn))
        data = self.get_json(self.PATH, headers=self.headers)

        # use precharge
        self.headers['X-User-Id'] = fake_data.ADMIN_USER_ID
        path = self.PATH + '/' + data[0]['code'] + '/used'
        result = self.put_json(path, {}, headers=self.headers)
        self.assertEqual(0, result.json['ret_code'])
        self.assertEqual(5, result.json['left_count'])

        # check precharge
        path = self.PATH + '/' + data[0]['code']
        precharge = self.get_json(path, headers=self.headers)

        self.assertEqual(data[0]['code'], precharge['code'])
        self.assertEqual(True, precharge['used'])

        # check account
        path = '/accounts/' + fake_data.ADMIN_USER_ID
        account = self.get_json(path, headers=self.headers)
        self.assertEqual('9100.0000', account['balance'])

        # reset left_count
        self.put_json(self.PATH, {}, headers=self.headers)

    def test_use_precharge_not_exist(self):
        self.headers['X-User-Id'] = fake_data.ADMIN_USER_ID
        path = self.PATH + '/fake_precharge/used'
        result = self.put_json(path, {}, headers=self.headers)
        self.assertEqual(1, result.json['ret_code'])
        self.assertEqual(4, result.json['left_count'])

        # reset left_count
        self.put_json(self.PATH, {}, headers=self.headers)

    def test_use_precharge_has_used(self):
        self.useFixture(db_fixtures.PrechargeInit(self.conn))
        data = self.get_json(self.PATH, headers=self.headers)

        # use precharge
        self.headers['X-User-Id'] = fake_data.ADMIN_USER_ID
        path = self.PATH + '/' + data[0]['code'] + '/used'
        result = self.put_json(path, {}, headers=self.headers)

        # use it again
        result = self.put_json(path, {}, headers=self.headers)
        self.assertEqual(2, result.json['ret_code'])
        self.assertEqual(4, result.json['left_count'])

        # reset left_count
        self.put_json(self.PATH, {}, headers=self.headers)

    def test_use_precharge_has_expired(self):
        # post a new precharge
        body = {
            "number": 1,
            "price": "100",
            "expired_at": datetime.datetime.utcnow().isoformat()
        }

        self.post_json(self.PATH, body, headers=self.headers)
        data = self.get_json(self.PATH, headers=self.headers)

        self.headers['X-User-Id'] = fake_data.ADMIN_USER_ID
        path = self.PATH + '/' + data[0]['code'] + '/used'
        result = self.put_json(path, {}, headers=self.headers)
        self.assertEqual(3, result.json['ret_code'])
        self.assertEqual(4, result.json['left_count'])

        # reset left_count
        self.put_json(self.PATH, {}, headers=self.headers)

    def test_use_precharge_exceed_count(self):
        # use precharge
        self.headers['X-User-Id'] = fake_data.ADMIN_USER_ID
        path = self.PATH + '/fake_code/used'
        result = self.put_json(path, {}, headers=self.headers)
        result = self.put_json(path, {}, headers=self.headers)
        result = self.put_json(path, {}, headers=self.headers)
        result = self.put_json(path, {}, headers=self.headers)
        result = self.put_json(path, {}, headers=self.headers)
        self.assertEqual(4, result.json['ret_code'])
        self.assertEqual(0, result.json['left_count'])

        # reset left_count
        self.put_json(self.PATH, {}, headers=self.headers)

    def test_put_precharge(self):
        # reset left_count
        result = self.put_json(self.PATH, {}, headers=self.headers)
        self.assertEqual(204, result.status_int)

    def test_put_precharge_403(self):
        # reset left_count
        del self.headers['X-Roles']
        result = self.put_json(self.PATH, {}, expect_errors=True, headers=self.headers)
        self.assertEqual(403, result.status_int)
