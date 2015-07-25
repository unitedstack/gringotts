
from oslo_config import cfg

from gringotts import constants as gring_const
from gringotts.openstack.common import jsonutils
from gringotts.openstack.common import log as logging
from gringotts.price import pricing
from gringotts.tests import service as test_service
from gringotts.waiter.plugins import floatingip

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class FloatingIpTestCase(test_service.WaiterServiceTestCase):

    def setUp(self):
        super(FloatingIpTestCase, self).setUp()

        self.event_created = floatingip.FloatingIpCreateEnd.event_types[0]
        self.event_resized = floatingip.FloatingIpResizeEnd.event_types[0]
        self.event_deleted = floatingip.FloatingIpDeleteEnd.event_types[0]

        self.publisher_id = 'network.master'
        self.floating_ip_address = '2.4.6.8'
        self.price_data = self.build_segmented_price_data(
            '5.0000', [[10, '0.1'], [4, '0.2'], [0, '0.3']])

    def set_product_floatingip_to_segmented_price(self):
        extra = {'price': self.price_data}
        product = self.product_fixture.ip_products[0]
        return self.update_product_in_db(product.product_id, extra=extra)

    def test_floatingip_created(self):
        handle = floatingip.FloatingIpCreateEnd()
        rate_limit = 1024
        project_id = self.admin_account.project_id

        payload = self.build_floatingip_payload(
            self.floating_ip_address, rate_limit, project_id)
        resource_id = payload['floatingip']['id']
        message = self.build_notification_message(
            self.event_created, payload, self.publisher_id)

        handle.process_notification(message)

        order = self.dbconn.get_order_by_resource_id(
            self.admin_req_context, resource_id)
        subs_list = list(self.dbconn.get_subscriptions_by_order_id(
            self.admin_req_context, order.order_id))
        self.assertEqual(1, len(subs_list))
        subs = subs_list[0]
        self.assertEqual(gring_const.STATE_RUNNING, subs.type)

        bill = self.dbconn.get_latest_bill(self.admin_req_context,
                                           order.order_id)
        self.assertEqual(resource_id, bill.resource_id)

    def test_floatingip_created_unit_price(self):
        handle = floatingip.FloatingIpCreateEnd()
        product = self.product_fixture.ip_products[0]
        project_id = self.admin_account.project_id

        # test rate_limit = 1024
        rate_limit = 1024
        payload = self.build_floatingip_payload(
            self.floating_ip_address, rate_limit, project_id)
        resource_id = payload['floatingip']['id']
        message = self.build_notification_message(
            self.event_created, payload, self.publisher_id)
        handle.process_notification(message)

        order = self.dbconn.get_order_by_resource_id(
            self.admin_req_context, resource_id)
        price = pricing.calculate_price(
            pricing.rate_limit_to_unit(rate_limit),
            product.unit_price)
        self.assertEqual(price, self.quantize(order.unit_price))

        # test rate_limit = 1024 * 11
        rate_limit = 1024 * 11
        payload = self.build_floatingip_payload(
            self.floating_ip_address, rate_limit, project_id)
        resource_id = payload['floatingip']['id']
        message = self.build_notification_message(
            self.event_created, payload, self.publisher_id)
        handle.process_notification(message)

        order = self.dbconn.get_order_by_resource_id(
            self.admin_req_context, resource_id)
        price = pricing.calculate_price(
            pricing.rate_limit_to_unit(rate_limit),
            product.unit_price)
        self.assertEqual(price, self.quantize(order.unit_price))

    def test_floatingip_created_segmented_price(self):
        handle = floatingip.FloatingIpCreateEnd()
        product = self.set_product_floatingip_to_segmented_price()
        extra = jsonutils.loads(product.extra)
        project_id = self.admin_account.project_id

        # test rate_limit = 1024
        rate_limit = 1024
        payload = self.build_floatingip_payload(
            self.floating_ip_address, rate_limit, project_id)
        resource_id = payload['floatingip']['id']
        message = self.build_notification_message(
            self.event_created, payload, self.publisher_id)
        handle.process_notification(message)

        order = self.dbconn.get_order_by_resource_id(
            self.admin_req_context, resource_id)
        price = pricing.calculate_price(
            pricing.rate_limit_to_unit(rate_limit),
            product.unit_price, extra['price']
        )
        self.assertEqual(price, self.quantize(order.unit_price))

        # test rate_limit = 1024 * 11
        rate_limit = 1024 * 11
        payload = self.build_floatingip_payload(
            self.floating_ip_address, rate_limit, project_id)
        resource_id = payload['floatingip']['id']
        message = self.build_notification_message(
            self.event_created, payload, self.publisher_id)
        handle.process_notification(message)

        order = self.dbconn.get_order_by_resource_id(
            self.admin_req_context, resource_id)
        price = pricing.calculate_price(
            pricing.rate_limit_to_unit(rate_limit),
            product.unit_price, extra['price']
        )
        self.assertEqual(price, self.quantize(order.unit_price))
