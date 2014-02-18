"""Test for resource operations within master"""

import mock
import datetime

from decimal import Decimal
from stevedore import extension

from gringotts import context
from gringotts import constants as const

from gringotts.openstack.common import timeutils

from gringotts.tests import fake_data
from gringotts.waiter import service as waiter_service
from gringotts.master import service as master_service
from gringotts.worker import service as worker_service
from gringotts.tests import db as db_test_base
from gringotts.tests import utils as test_utils


class TestMasterService(db_test_base.DBTestBase):

    def setUp(self):
        super(TestMasterService, self).setUp()

        self.useFixture(db_test_base.DatabaseInit(self.conn))

        self.waiter_srv = waiter_service.WaiterService('the-host', 'the-topic')
        self.master_srv = master_service.MasterService()

        with mock.patch('gringotts.openstack.common.rpc.create_connection'):
            self.master_srv.start()
            self.waiter_srv.start()

        self.ctxt = context.get_admin_context()
        self.instance_id = 'b3725586-ae77-4001-9ecb-c0b4afb35904'

    @mock.patch('gringotts.master.api.API.resource_created', mock.MagicMock())
    def test_resource_create_end(self):
        self.waiter_srv.process_notification(fake_data.NOTICE_INSTANCE_CREATE_END)

        order = self.conn.get_order_by_resource_id(self.ctxt,
                                                   self.instance_id)

        action_time = fake_data.INSTANCE_CREATED_TIME
        remarks = 'Instance Has Been Created.'
        self.master_srv.resource_created(self.ctxt, order.order_id,
                                         action_time, remarks)

        bills = self.conn.get_bills_by_order_id(self.ctxt, order.order_id)
        bills = list(bills)
        self.assertEqual(1, len(bills))

        action_time = timeutils.parse_strtime(action_time,
                                              fmt=worker_service.TIMESTAMP_TIME_FORMAT)
        bill_end_time = action_time + datetime.timedelta(hours=1)

        bill_end_time = test_utils.remove_microsecond(bill_end_time)
        actual = test_utils.remove_microsecond(bills[0].end_time)
        self.assertEqual(bill_end_time, actual)

        cron_jobs = self.master_srv.apsched.get_jobs()
        self.assertEqual(1, len(cron_jobs))

    @mock.patch('gringotts.master.api.API.resource_created', mock.MagicMock())
    def test_resource_change_end(self):
        # Create an instance
        self.waiter_srv.process_notification(fake_data.NOTICE_INSTANCE_CREATE_END)

        order = self.conn.get_order_by_resource_id(self.ctxt,
                                                   self.instance_id)

        action_time = fake_data.INSTANCE_CREATED_TIME
        remarks = 'Instance Has Been Created.'
        self.master_srv.resource_created(self.ctxt, order.order_id,
                                         action_time, remarks)

        # Stop the instance
        action_time = fake_data.INSTANCE_STOPPED_TIME
        remarks = 'Instance Has Been Stopped.'
        change_to = const.STATE_STOPPED
        self.master_srv.resource_changed(self.ctxt, order.order_id,
                                         action_time, change_to, remarks)

        # Assertions
        bills = self.conn.get_bills_by_order_id(self.ctxt, order.order_id)

        # Check bills
        bills = list(bills)
        self.assertEqual(2, len(bills))
        self.assertEqual(Decimal('0.0150'), bills[0].total_price)

        action_time = timeutils.parse_strtime(action_time,
                                              fmt=worker_service.TIMESTAMP_TIME_FORMAT)
        bill_end_time = action_time + datetime.timedelta(hours=1)

        bill_end_time = test_utils.remove_microsecond(bill_end_time)
        actual = test_utils.remove_microsecond(bills[1].end_time)
        self.assertEqual(bill_end_time, actual)

        # Check apscheduler cron jobs
        cron_jobs = self.master_srv.apsched.get_jobs()
        self.assertEqual(1, len(cron_jobs))

        # Check the updated order
        order = self.conn.get_order_by_resource_id(self.ctxt,
                                                   self.instance_id)
        self.assertEqual('stopped', order.status)
        self.assertEqual(Decimal('0.0020'), order.unit_price)
        self.assertEqual(Decimal('0.0170'), order.total_price)

    @mock.patch('gringotts.master.api.API.resource_created', mock.MagicMock())
    def test_resource_delete_end(self):
        # Create an instance
        self.waiter_srv.process_notification(fake_data.NOTICE_INSTANCE_CREATE_END)

        order = self.conn.get_order_by_resource_id(self.ctxt,
                                                   self.instance_id)

        action_time = fake_data.INSTANCE_CREATED_TIME
        remarks = 'Instance Has Been Created.'
        self.master_srv.resource_created(self.ctxt, order.order_id,
                                         action_time, remarks)

        # Delete the instance
        action_time = fake_data.INSTANCE_DELETED_TIME
        self.master_srv.resource_deleted(self.ctxt, order.order_id, action_time)

        # Assertions
        bills = self.conn.get_bills_by_order_id(self.ctxt, order.order_id)

        # Check bills
        bills = list(bills)
        self.assertEqual(1, len(bills))
        self.assertEqual(Decimal('0.0450'), bills[0].total_price)

        action_time = timeutils.parse_strtime(action_time,
                                              fmt=worker_service.TIMESTAMP_TIME_FORMAT)

        bill_end_time = test_utils.remove_microsecond(action_time)
        actual = test_utils.remove_microsecond(bills[0].end_time)
        self.assertEqual(bill_end_time, actual)

        # Check apscheduler cron jobs
        cron_jobs = self.master_srv.apsched.get_jobs()
        self.assertEqual(0, len(cron_jobs))

        # Check the updated order
        order = self.conn.get_order_by_resource_id(self.ctxt,
                                                   self.instance_id)
        self.assertEqual('deleted', order.status)
        self.assertEqual(Decimal('0.0000'), order.unit_price)
        self.assertEqual(Decimal('0.0450'), order.total_price)

    @mock.patch('gringotts.master.api.API.resource_created', mock.MagicMock())
    def test_resource_resize_end(self):
        # Create a volume
        self.waiter_srv.process_notification(fake_data.NOTICE_VOLUME_CREATE_END)

        volume_id = '7d0e2a0f-15dc-47f1-bb63-27513c6ab431'
        order = self.conn.get_order_by_resource_id(self.ctxt, volume_id)

        action_time = fake_data.VOLUME_CREATED_TIME
        remarks = 'Instance Has Been Created.'
        self.master_srv.resource_created(self.ctxt, order.order_id,
                                         action_time, remarks)

        # Resize the instance
        action_time = fake_data.VOLUME_RESIZED_TIME
        remarks = 'Volume Has Been Resized.'
        quantity = 4 # resize size
        self.master_srv.resource_resized(self.ctxt, order.order_id,
                                         action_time, quantity, remarks)

        # Assertions
        bills = self.conn.get_bills_by_order_id(self.ctxt, order.order_id)

        # Check bills
        bills = list(bills)
        self.assertEqual(2, len(bills))
        self.assertEqual(Decimal('0.0007'), bills[0].total_price)

        action_time = timeutils.parse_strtime(action_time,
                                              fmt=worker_service.TIMESTAMP_TIME_FORMAT)
        bill_end_time = action_time + datetime.timedelta(hours=1)

        bill_end_time = test_utils.remove_microsecond(bill_end_time)
        actual = test_utils.remove_microsecond(bills[1].end_time)
        self.assertEqual(bill_end_time, actual)

        # Check apscheduler cron jobs
        cron_jobs = self.master_srv.apsched.get_jobs()
        self.assertEqual(1, len(cron_jobs))

        # Check the updated order
        order = self.conn.get_order_by_resource_id(self.ctxt,
                                                   volume_id)
        self.assertEqual('running', order.status)
        self.assertEqual(Decimal('0.0080'), order.unit_price)
        self.assertEqual(Decimal('0.0087'), order.total_price)
