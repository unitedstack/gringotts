
from gringotts import constants as gring_const
from gringotts.openstack.common import log as logging
from gringotts.tests import rest

LOG = logging.getLogger(__name__)


class OrderTestCase(rest.RestfulTestCase):

    def setUp(self):
        super(OrderTestCase, self).setUp()

        self.order_path = '/v2/orders'
        self.summary_path = '/v2/orders/summary'
        self.admin_headers = self.build_admin_http_headers()

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
        self.post(self.order_path, headers=self.admin_headers,
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
        self.put(self.order_path, headers=self.admin_headers,
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

    def _create_bill(self, product, product_type):
        user_id = self.admin_account.user_id
        project_id = self.admin_account.project_id

        quantity = 1
        order_id = self.new_order_id()
        subs = self.create_subs_in_db(
            product, quantity, gring_const.STATE_RUNNING,
            order_id, project_id, user_id)
        order = self.create_order_in_db(
            str(subs.unit_price), subs.unit, user_id, project_id,
            product_type, subs.type, order_id=order_id)

        start_time = self.utcnow()
        self.dbconn.create_bill(self.admin_req_context, order.order_id,
                                action_time=start_time)
        bill = self.dbconn.get_latest_bill(self.admin_req_context,
                                           order.order_id)
        order = self.dbconn.get_order(self.admin_req_context, order.order_id)
        LOG.debug('order_id(%s), total_price(%s)',
                  order.order_id, order.total_price)
        return bill.total_price

    def _get_order_summary(self, order_type, summary_ref):
        for s in summary_ref['summaries']:
            if s['order_type'] == order_type:
                return s

    def test_get_orders_summary(self):
        instance_product = self.product_fixture.instance_products[0]
        instance_total_price = self._create_bill(
            instance_product, gring_const.RESOURCE_INSTANCE)

        fip_product = self.product_fixture.ip_products[0]
        fip_total_price = self._create_bill(
            fip_product, gring_const.RESOURCE_FLOATINGIP)

        total_price = instance_total_price + fip_total_price

        query_url = '%s?project_id=%s' % (self.summary_path,
                                          self.admin_account.project_id)
        resp = self.get(query_url, headers=self.admin_headers)
        summary_ref = resp.json_body
        self.assertEqual(2, summary_ref['total_count'])
        self.assertDecimalEqual(total_price, summary_ref['total_price'])

        instance_ref = self._get_order_summary(
            gring_const.RESOURCE_INSTANCE, summary_ref)
        self.assertEqual(1, instance_ref['total_count'])
        self.assertDecimalEqual(
            instance_total_price, instance_ref['total_price'])

        fip_ref = self._get_order_summary(
            gring_const.RESOURCE_FLOATINGIP, summary_ref)
        self.assertEqual(1, fip_ref['total_count'])
        self.assertDecimalEqual(fip_total_price, fip_ref['total_price'])

    def test_get_orders_summary_with_floatingipset(self):
        fip_product = self.product_fixture.ip_products[0]
        fip_total_price = self._create_bill(
            fip_product, gring_const.RESOURCE_FLOATINGIP)

        fipset_product = self.product_fixture.ip_products[1]
        fipset_total_price = self._create_bill(
            fipset_product, gring_const.RESOURCE_FLOATINGIPSET)

        total_price = fip_total_price + fipset_total_price

        query_url = '%s?project_id=%s' % (self.summary_path,
                                          self.admin_account.project_id)
        resp = self.get(query_url, headers=self.admin_headers)
        summary_ref = resp.json_body
        self.assertEqual(2, summary_ref['total_count'])
        self.assertDecimalEqual(total_price, summary_ref['total_price'])

        fip_ref = self._get_order_summary(
            gring_const.RESOURCE_FLOATINGIP, summary_ref)
        self.assertEqual(2, fip_ref['total_count'])
        self.assertDecimalEqual(total_price, fip_ref['total_price'])

    def test_get_order_detail_with_negative_limit_or_offset(self):
        order_id = self.new_order_id()
        path = "%s/%s" % (self.order_path, order_id)
        self.check_invalid_limit_or_offset(path)

    def test_get_all_orders_with_negative_limit_or_offset(self):
        path = self.order_path
        self.check_invalid_limit_or_offset(path)

    def test_get_active_orders_with_negative_limit_or_offset(self):
        path = "%s/%s" % (self.order_path, 'active')
        self.check_invalid_limit_or_offset(path)

    def test_activate_auto_renew(self):
        pass
