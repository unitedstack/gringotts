"""Test for resource operations within master"""

import mock

from oslotest import mockpatch

from gringotts import constants as gring_const
from gringotts.tests import service as test_service


class MasterServiceBasicTestCase(test_service.MasterServiceTestCase):

    def setUp(self):
        super(MasterServiceBasicTestCase, self).setUp()

        http_headers = self.build_admin_http_headers()
        mocked_get_auth_headers = mock.MagicMock(return_value=http_headers)
        self.useFixture(mockpatch.PatchObject(
            self.client.auth_plugin, 'get_auth_headers',
            mocked_get_auth_headers
        ))

    def test_resource_created(self):
        product = self.product_fixture.instance_products[0]
        resource_volume = 1
        resource_type = gring_const.RESOURCE_INSTANCE
        order_id = self.new_order_id()
        user_id = self.admin_account.user_id
        project_id = self.admin_account.project_id

        subs = self.create_subs_in_db(
            product, resource_volume, gring_const.STATE_RUNNING,
            order_id, project_id, user_id
        )
        order = self.create_order_in_db(
            float(self.quantize(subs.unit_price)) * resource_volume,
            subs.unit, user_id, project_id, resource_type,
            subs.type, order_id=order_id
        )

        action_time = self.utcnow()
        self.service.resource_created(
            self.admin_req_context, order.order_id,
            self.datetime_to_str(action_time), 'remarks')

        bill = self.dbconn.get_latest_bill(self.admin_req_context,
                                           order.order_id)
        self.assertEqual(order.order_id, bill.order_id)
        self.assertEqual(action_time, bill.start_time)

    def test_resource_created_again(self):
        pass

    def test_resource_deleted(self):
        pass

    def test_resource_stopped(self):
        pass

    def test_resource_started(self):
        pass

    def test_resource_changed(self):
        pass

    def test_resource_resized(self):
        pass

    def test_instance_stopped(self):
        pass

    def test_instance_resized(self):
        pass
