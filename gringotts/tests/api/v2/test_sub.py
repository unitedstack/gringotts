import datetime

from gringotts import context
from gringotts.tests import db_fixtures
from gringotts.tests import fake_data
from gringotts.tests.api.v2 import FunctionalTest


class TestSubscriptions(FunctionalTest):
    PATH = '/subs'

    def setUp(self):
        super(TestSubscriptions, self).setUp()
        self.useFixture(db_fixtures.DatabaseInit(self.conn))
        self.headers = {'X-Roles': 'admin'}

    def test_post_subscription(self):
        body = {
            "product_name": "instance:m1.tiny",
            "service": "compute",
            "region_id": "RegionOne",
            "resource_volume": 1,
            "order_id": "fake_order_id",
            "type": "running",
            "user_id": fake_data.DEMO_USER_ID,
            "project_id": fake_data.DEMO_PROJECT_ID,
        }
        self.post_json(self.PATH, body, headers=self.headers)

        subs = self.conn.get_subscriptions_by_order_id(context.get_admin_context(),
                                                       'fake_order_id')
        subs = [sub for sub in subs]
        self.assertEqual(fake_data.PRODUCT_FLAVOR_TINY['product_id'], subs[0]['product_id'])

    def test_put_subscription(self):
        new_sub = {
            "product_name": "volume.size",
            "service": "block_storage",
            "region_id": "RegionOne",
            "resource_volume": 10,
            "order_id": "fake_order_id",
            "type": "running",
            "user_id": fake_data.DEMO_USER_ID,
            "project_id": fake_data.DEMO_PROJECT_ID,
        }
        self.post_json(self.PATH, new_sub, headers=self.headers)

        body = {
            "order_id": "fake_order_id",
            "change_to": "running",
            "quantity": 20
        }
        self.put_json(self.PATH, body, headers=self.headers)

        subs = self.conn.get_subscriptions_by_order_id(context.get_admin_context(),
                                                       'fake_order_id')
        subs = [sub for sub in subs]
        self.assertEqual(20, subs[0]['quantity'])

    def test_put_flavor_subscription(self):
        new_sub = {
            "product_name": "instance:m1.tiny",
            "service": "compute",
            "region_id": "RegionOne",
            "resource_volume": 1,
            "order_id": "fake_order_id",
            "type": "running",
            "user_id": fake_data.DEMO_USER_ID,
            "project_id": fake_data.DEMO_PROJECT_ID,
        }
        self.post_json(self.PATH, new_sub, headers=self.headers)

        body = {
            "service": "compute",
            "region_id": "RegionOne",
            "old_flavor": "instance:m1.tiny",
            "new_flavor": "instance:m1.small",
            "order_id": "fake_order_id",
            "change_to": "running",
        }
        self.put_json(self.PATH, body, headers=self.headers)

        subs = self.conn.get_subscriptions_by_order_id(context.get_admin_context(),
                                                       'fake_order_id')
        subs = [sub for sub in subs]
        self.assertEqual('0.1110', str(subs[0]['unit_price']))
        self.assertEqual(fake_data.PRODUCT_FLAVOR_SMALL['product_id'], subs[0]['product_id'])
