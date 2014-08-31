import fixtures
import mock
import datetime

from gringotts import context
from gringotts import constants as const
from gringotts.db import models as db_models
from gringotts.tests import fake_data

from gringotts.waiter import service as waiter_service
from gringotts.master import service as master_service
from gringotts.worker import service as worker_service


class DatabaseInit(fixtures.Fixture):
    def __init__(self, conn):
        self.conn = conn

    def setUp(self):
        super(DatabaseInit, self).setUp()
        self.prepare_data()
        self.addCleanup(self.reset)

    def prepare_data(self):
        product_flavor_tiny = db_models.Product(**fake_data.PRODUCT_FLAVOR_TINY)
        product_flavor_small = db_models.Product(**fake_data.PRODUCT_FLAVOR_SMALL)
        product_volume_size = db_models.Product(**fake_data.PRODUCT_VOLUME_SIZE)
        product_router_size = db_models.Product(**fake_data.PRODUCT_ROUTER_SIZE)
        product_snapshot_size = db_models.Product(**fake_data.PRODUCT_SNAPSHOT_SIZE)
        product_image_license = db_models.Product(**fake_data.PRODUCT_IMAGE_LICENSE)

        fake_account_demo = db_models.Account(**fake_data.FAKE_ACCOUNT_DEMO)
        fake_account_admin = db_models.Account(**fake_data.FAKE_ACCOUNT_ADMIN)

        fake_project_demo = db_models.Project(**fake_data.FAKE_PROJECT_DEMO)
        fake_project_admin = db_models.Project(**fake_data.FAKE_PROJECT_ADMIN)

        self.conn.create_product(context.get_admin_context(),
                                 product_flavor_tiny)
        self.conn.create_product(context.get_admin_context(),
                                 product_flavor_small)
        self.conn.create_product(context.get_admin_context(),
                                 product_volume_size)
        self.conn.create_product(context.get_admin_context(),
                                 product_router_size)
        self.conn.create_product(context.get_admin_context(),
                                 product_snapshot_size)
        self.conn.create_product(context.get_admin_context(),
                                 product_image_license)
        self.conn.create_account(context.get_admin_context(),
                                 fake_account_demo)
        self.conn.create_account(context.get_admin_context(),
                                 fake_account_admin)
        self.conn.create_project(context.get_admin_context(),
                                 fake_project_demo)
        self.conn.create_project(context.get_admin_context(),
                                 fake_project_admin)

    def reset(self):
        self.conn.clear()
        self.conn = None


class GenerateFakeData(fixtures.Fixture):

    def __init__(self, conn):
        self.conn = conn

    def setUp(self):
        super(GenerateFakeData, self).setUp()

        self.ctxt = context.get_admin_context()
        self.waiter_srv = waiter_service.WaiterService('the-host', 'the-topic')
        self.master_srv = master_service.MasterService()

        with mock.patch('gringotts.openstack.common.rpc.create_connection'):
            self.master_srv.start()
            self.waiter_srv.start()

        self.generate_fake_data()
        self.addCleanup(self.reset)

    def reset(self):
        self.conn.clear()
        self.conn = None

    def generate_fake_data(self):

        # instance 1 (running)
        self.instance_create_end(fake_data.NOTICE_INSTANCE_1_CREATED)

        # instance 2 (running, stopped)
        self.instance_create_end(fake_data.NOTICE_INSTANCE_2_CREATED)
        self.instance_stop_end(fake_data.NOTICE_INSTANCE_2_STOPPED)

        # instance 3 (running, stopped, running)
        self.instance_create_end(fake_data.NOTICE_INSTANCE_3_CREATED)
        self.instance_stop_end(fake_data.NOTICE_INSTANCE_3_STOPPED)
        self.instance_start_end(fake_data.NOTICE_INSTANCE_3_STARTED)

        # instance 4 (running, stopped, running, deleted)
        self.instance_create_end(fake_data.NOTICE_INSTANCE_4_CREATED)
        self.instance_stop_end(fake_data.NOTICE_INSTANCE_4_STOPPED)
        self.instance_start_end(fake_data.NOTICE_INSTANCE_4_STARTED)
        self.instance_delete_end(fake_data.NOTICE_INSTANCE_4_DELETED)

        # instance 5 (running, resized)
        self.instance_create_end(fake_data.NOTICE_INSTANCE_5_CREATED)
        self.instance_resize_end(fake_data.NOTICE_INSTANCE_5_RESIZED)

        # volume 1 (running)
        self.volume_create_end(fake_data.NOTICE_VOLUME_1_CREATED)

        # volume 2 (running, running)
        self.volume_create_end(fake_data.NOTICE_VOLUME_2_CREATED)
        self.volume_resize_end(fake_data.NOTICE_VOLUME_2_RESIZED)

        # router 1 (running)
        self.router_create_end(fake_data.NOTICE_ROUTER_1_CREATED)

    @mock.patch('gringotts.master.api.API.resource_created', mock.MagicMock())
    def instance_create_end(self, message):
        self.waiter_srv.process_notification(message)

        order = self.conn.get_order_by_resource_id(self.ctxt,
                                                   message['payload']['instance_id'])
        action_time = message['timestamp']
        remarks = 'Instance Has Been Created.'
        self.master_srv.resource_created(self.ctxt, order.order_id,
                                         action_time, remarks)

    def instance_stop_end(self, message):
        order = self.conn.get_order_by_resource_id(self.ctxt,
                                                   message['payload']['instance_id'])
        action_time = message['timestamp']
        change_to = const.STATE_STOPPED
        self.master_srv.instance_stopped(self.ctxt, order.order_id, action_time)

    def instance_start_end(self, message):
        order = self.conn.get_order_by_resource_id(self.ctxt,
                                                   message['payload']['instance_id'])
        action_time = message['timestamp']
        remarks = 'Instance Has Been Started.'
        change_to = const.STATE_RUNNING
        self.master_srv.resource_changed(self.ctxt, order.order_id,
                                         action_time, change_to, remarks)

    def instance_resize_end(self, message):
        order = self.conn.get_order_by_resource_id(self.ctxt,
                                                   message['payload']['instance_id'])

        new_flavor = message['payload']['instance_type']
        old_flavor = message['payload']['old_instance_type']

        new_flavor = '%s:%s' % (const.PRODUCT_INSTANCE_TYPE_PREFIX,
                                new_flavor)
        old_flavor = '%s:%s' % (const.PRODUCT_INSTANCE_TYPE_PREFIX,
                                old_flavor)
        service = const.SERVICE_COMPUTE
        region_id = "RegionOne"

        action_time = message['timestamp']
        remarks = 'Instance Has Been Resized'
        self.master_srv.instance_resized(self.ctxt, order.order_id, action_time,
                                         new_flavor, old_flavor,
                                         service, region_id, remarks)

    def instance_delete_end(self, message):
        order = self.conn.get_order_by_resource_id(self.ctxt,
                                                   message['payload']['instance_id'])
        action_time = message['timestamp']
        self.master_srv.resource_deleted(self.ctxt, order.order_id, action_time,
                                         "Instance Has Been Deleted")

    @mock.patch('gringotts.master.api.API.resource_created', mock.MagicMock())
    def volume_create_end(self, message):
        self.waiter_srv.process_notification(message)
        order = self.conn.get_order_by_resource_id(self.ctxt,
                                                   message['payload']['volume_id'])
        action_time = message['timestamp']
        remarks = 'Volume Has Been Created.'
        self.master_srv.resource_created(self.ctxt, order.order_id, action_time,
                                         remarks)

    def volume_resize_end(self, message):
        order = self.conn.get_order_by_resource_id(self.ctxt,
                                                   message['payload']['volume_id'])
        action_time = message['timestamp']
        remarks = 'Instance Has Been Resized.'
        quantity = message['payload']['size']
        self.master_srv.resource_resized(self.ctxt, order.order_id, action_time,
                                         quantity, remarks)

    def volume_delete_end(self, message):
        order = self.conn.get_order_by_resource_id(self.ctxt,
                                                   message['payload']['volume_id'])
        action_time = message['timestamp']
        self.master_srv.resource_deleted(self.ctxt, order.order_id, action_time,
                                         "Volume Has Been Deleted")

    @mock.patch('gringotts.master.api.API.resource_created', mock.MagicMock())
    def router_create_end(self, message):
        self.waiter_srv.process_notification(message)
        order = self.conn.get_order_by_resource_id(self.ctxt,
                                                   message['payload']['router']['id'])
        action_time = message['timestamp']
        remarks = 'Router Has Been Created.'
        self.master_srv.resource_created(self.ctxt, order.order_id, action_time,
                                         remarks)

    def router_delete_end(self, message):
        order = self.conn.get_order_by_resource_id(self.ctxt,
                                                   message['payload']['router']['id'])
        action_time = message['timestamp']
        self.master_srv.resource_deleted(self.ctxt, order.order_id, action_time,
                                         "Router Has Been Deleted")


class PrechargeInit(fixtures.Fixture):
    def __init__(self, conn):
        self.conn = conn

    def setUp(self):
        super(PrechargeInit, self).setUp()
        self.generate_precharge()
        self.addCleanup(self.reset)

    def generate_precharge(self):
        expired_at = datetime.datetime.utcnow() + datetime.timedelta(days=365)

        self.conn.create_precharge(context.get_admin_context(),
                                   number=10,
                                   price="125",
                                   expired_at=expired_at)

    def reset(self):
        self.conn.clear()
        self.conn = None
