"""Test for instance operations within waiter"""

import mock
from stevedore import extension
from decimal import Decimal

from gringotts import context
from gringotts import constants as const

from gringotts.tests import fake_data
from gringotts.tests import db_fixtures
from gringotts.waiter import service as waiter_service
from gringotts.tests import db as db_test_base


class TestWaiterService(db_test_base.DBTestBase):

    def setUp(self):
        super(TestWaiterService, self).setUp()

        self.useFixture(db_fixtures.DatabaseInit(self.conn))

        self.srv = waiter_service.WaiterService('the-host', 'the-topic')
        with mock.patch('gringotts.openstack.common.rpc.create_connection'):
            self.srv.start()

        self.ctxt = context.get_admin_context()
        self.instance_id = 'b3725586-ae77-4001-9ecb-c0b4afb35904'

    def test_instance_create_end(self):
        with mock.patch('gringotts.master.api.API.resource_created') as resource_created:
            self.srv.process_notification(fake_data.NOTICE_INSTANCE_1_CREATED)
            order = self.conn.get_order_by_resource_id(self.ctxt,
                                                       fake_data.INSTANCE_ID_1)

            self.assertEqual(fake_data.INSTANCE_ID_1, order.resource_id)
            self.assertEqual(Decimal('0.09'), order.unit_price)

            subs = self.conn.get_subscriptions_by_order_id(self.ctxt, order.order_id)
            self.assertEqual(4, len(list(subs)))

            action_time = fake_data.INSTANCE_1_CREATED_TIME
            remarks = 'Instance Has Been Created.'
            resource_created.assert_called_with(self.ctxt, order.order_id,
                                                action_time, remarks)

    @mock.patch('gringotts.master.api.API.resource_created', mock.MagicMock())
    def test_instance_stop_end(self):
        with mock.patch('gringotts.master.api.API.instance_stopped') as instance_stopped:
            self.srv.process_notification(fake_data.NOTICE_INSTANCE_1_CREATED)
            self.srv.process_notification(fake_data.NOTICE_INSTANCE_1_STOPPED)

            order = self.conn.get_order_by_resource_id(self.ctxt,
                                                       fake_data.INSTANCE_ID_1)

            action_time = fake_data.INSTANCE_1_STOPPED_TIME
            change_to = const.STATE_STOPPED

            instance_stopped.assert_called_with(self.ctxt, order.order_id, action_time)

    @mock.patch('gringotts.master.api.API.resource_created', mock.MagicMock())
    def test_instance_start_end(self):
        with mock.patch('gringotts.master.api.API.resource_changed') as resource_changed:
            self.srv.process_notification(fake_data.NOTICE_INSTANCE_1_CREATED)
            self.srv.process_notification(fake_data.NOTICE_INSTANCE_1_STARTED)

            order = self.conn.get_order_by_resource_id(self.ctxt,
                                                       fake_data.INSTANCE_ID_1)

            action_time = fake_data.INSTANCE_1_STARTED_TIME
            remarks = 'Instance Has Been Started.'
            change_to = const.STATE_RUNNING

            resource_changed.assert_called_with(self.ctxt, order.order_id,
                                                action_time, change_to,
                                                remarks)

    @mock.patch('gringotts.master.api.API.resource_created', mock.MagicMock())
    def test_instance_delete_end(self):
        with mock.patch('gringotts.master.api.API.resource_deleted') as resource_deleted:
            self.srv.process_notification(fake_data.NOTICE_INSTANCE_1_CREATED)
            self.srv.process_notification(fake_data.NOTICE_INSTANCE_1_DELETED)

            order = self.conn.get_order_by_resource_id(self.ctxt,
                                                       fake_data.INSTANCE_ID_1)

            action_time = fake_data.INSTANCE_1_DELETED_TIME

            resource_deleted.assert_called_with(self.ctxt, order.order_id,
                                                action_time)
