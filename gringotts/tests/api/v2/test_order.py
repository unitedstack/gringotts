
from gringotts import constants as gring_const
from gringotts.tests import rest


class OrderTestCase(rest.RestfulTestCase):

    def setUp(self):
        super(OrderTestCase, self).setUp()

        self.order_path = '/v2/orders'
        self.headers = self.build_admin_http_headers()

    def test_create_order(self):
        product = self.product_fixture.instance_products[0]
        resource_volume = 1
        resource_type = gring_const.RESOURCE_INSTANCE
        status = gring_const.STATE_RUNNING
        order_id = self.new_order_id()
        user_id = self.admin_account.user_id
        project_id = self.admin_account.project_id

        subs = self.create_subs_in_db(product, resource_volume, status,
                                      order_id, project_id, user_id)

        order_price = float(self.quantize(subs.unit_price * resource_volume))
        order_ref = self.new_order_ref(
            order_price, subs.unit, user_id, project_id,
            resource_type, status, order_id
        )
        self.post(self.order_path, headers=self.headers,
                  body=order_ref, expected_status=204)

        order = self.dbconn.get_order(self.admin_req_context, order_id)
        self.assertOrderEqual(order_ref, order.as_dict())

    def test_order_change_state(self):
        product = self.product_fixture.instance_products[0]
        resource_volume = 1
        resource_type = gring_const.RESOURCE_INSTANCE
        order_id = self.new_order_id()
        user_id = self.admin_account.user_id
        project_id = self.admin_account.project_id

        running_subs = self.create_subs_in_db(
            product, resource_volume, gring_const.STATE_RUNNING,
            order_id, project_id, user_id
        )
        stopped_subs = self.create_subs_in_db(
            product, resource_volume, gring_const.STATE_STOPPED,
            order_id, project_id, user_id,
        )
        self.create_order_in_db(
            float(self.quantize(running_subs.unit_price)),
            running_subs.unit, user_id, project_id, resource_type,
            running_subs.type, order_id=order_id
        )
        order_put_ref = self.new_order_put_ref(order_id,
                                               stopped_subs.type)
        self.put(self.order_path, headers=self.headers,
                 body=order_put_ref)
        new_order = self.dbconn.get_order(self.admin_req_context, order_id)
        self.assertEqual(stopped_subs.type, new_order.status)

    def test_get_all_orders(self):
        pass

    def test_get_all_orders_with_pagination(self):
        pass

    def test_get_orders_by_user_id(self):
        pass

    def test_get_orders_by_project_id(self):
        pass

    def test_get_orders_by_user_id_and_time_range(self):
        pass

    def test_get_orders_by_project_id_and_time_range(self):
        pass

    def test_get_order_summary(self):
        pass
