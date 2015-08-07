
import datetime

import mock
from oslo_config import cfg
from oslotest import mockpatch

from gringotts import constants as gring_const
from gringotts.openstack.common import jsonutils
from gringotts.openstack.common import log as logging
from gringotts.price import pricing
from gringotts.services import keystone
from gringotts.services import lotus
from gringotts.tests import service as test_service
from gringotts.tests import utils as test_utils
from gringotts.waiter.plugins import floatingip

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class FloatingIpTestCase(test_service.WaiterServiceTestCase):

    def setUp(self):
        super(FloatingIpTestCase, self).setUp()

        self.event_created = floatingip.EVENT_FLOATINGIP_CREATE_END
        self.event_resized = floatingip.EVENT_FLOATINGIP_RESIZE_END
        self.event_deleted = floatingip.EVENT_FLOATINGIP_DELETE_END

        self.floating_ip_address = '2.4.6.8'
        self.price_data = self.build_segmented_price_data(
            '5.0000', [[10, '0.1'], [4, '0.2'], [0, '0.3']])

        self.useFixture(mockpatch.PatchObject(
            floatingip.FloatingIpNotificationBase,
            '_send_email_notification'))

    def set_product_floatingip_to_segmented_price(self):
        extra = {'price': self.price_data}
        product = self.product_fixture.ip_products[0]
        return self.update_product_in_db(product.product_id, extra=extra)

    def create_floatingip(self, rate_limit, project_id, timestamp=None):
        handle = floatingip.FloatingIpCreateEnd()
        payload = self.build_floatingip_payload(
            self.floating_ip_address, rate_limit, project_id)
        resource_id = payload['floatingip']['id']
        message = self.build_notification_message(
            self.admin_account.user_id, self.event_created, payload,
            timestamp=timestamp)
        handle.process_notification(message)
        return resource_id

    def test_floatingip_create_end(self):
        product = self.product_fixture.ip_products[0]
        rate_limit = 1024
        quantity = pricing.rate_limit_to_unit(rate_limit)
        price = pricing.calculate_price(quantity, product.unit_price)
        project_id = self.admin_account.project_id
        start_time = self.utcnow()

        resource_id = self.create_floatingip(
            rate_limit, project_id, timestamp=start_time)

        order = self.dbconn.get_order_by_resource_id(
            self.admin_req_context, resource_id)
        self.assertDecimalEqual(price, order.unit_price)
        subs_list = list(self.dbconn.get_subscriptions_by_order_id(
            self.admin_req_context, order.order_id))
        self.assertEqual(1, len(subs_list))
        for subs in subs_list:
            self.assertEqual(gring_const.STATE_RUNNING, subs.type)
            self.assertEqual(quantity, subs.quantity)

        bill = self.dbconn.get_latest_bill(self.admin_req_context,
                                           order.order_id)
        self.assertEqual(resource_id, bill.resource_id)
        self.assertEqual(self.datetime_to_str(start_time),
                         self.datetime_to_str(bill.start_time))
        self.assertDecimalEqual(price, bill.unit_price)

    def test_floatingip_create_end_unit_price(self):
        product = self.product_fixture.ip_products[0]
        project_id = self.admin_account.project_id

        def _test_floatingip_created_unit_price(rate_limit):
            price = pricing.calculate_price(
                pricing.rate_limit_to_unit(rate_limit), product.unit_price)
            resource_id = self.create_floatingip(rate_limit, project_id)
            order = self.dbconn.get_order_by_resource_id(
                self.admin_req_context, resource_id)
            self.assertDecimalEqual(price, order.unit_price)
            bill = self.dbconn.get_latest_bill(self.admin_req_context,
                                               order.order_id)
            self.assertDecimalEqual(price, bill.unit_price)

        _test_floatingip_created_unit_price(1024)
        _test_floatingip_created_unit_price(1024 * 11)

    def test_floatingip_create_end_segmented_price(self):
        product = self.set_product_floatingip_to_segmented_price()
        extra = jsonutils.loads(product.extra)
        project_id = self.admin_account.project_id

        def _test_floatingip_created_segmented_price(rate_limit):
            price = pricing.calculate_price(
                pricing.rate_limit_to_unit(rate_limit),
                product.unit_price, extra['price'])
            resource_id = self.create_floatingip(rate_limit, project_id)
            order = self.dbconn.get_order_by_resource_id(
                self.admin_req_context, resource_id)
            self.assertDecimalEqual(price, order.unit_price)
            bill = self.dbconn.get_latest_bill(self.admin_req_context,
                                               order.order_id)
            self.assertDecimalEqual(price, bill.unit_price)

        _test_floatingip_created_segmented_price(1024)
        _test_floatingip_created_segmented_price(1024 * 11)

    def test_floatingip_resize_end(self):
        product = self.product_fixture.ip_products[0]
        project_id = self.admin_account.project_id
        end_time = self.utcnow()
        start_time = end_time - datetime.timedelta(hours=1)

        # rate_limit = 1024
        rate_limit = 1024
        resource_id = self.create_floatingip(
            rate_limit, project_id, timestamp=start_time)
        order = self.dbconn.get_order_by_resource_id(
            self.admin_req_context, resource_id)
        bill1 = self.dbconn.get_latest_bill(self.admin_req_context,
                                            order.order_id)

        # change rate_limit to 1024 * 11
        rate_limit = 1024 * 11
        quantity = pricing.rate_limit_to_unit(rate_limit)
        payload = self.build_floatingip_payload(
            self.floating_ip_address, rate_limit, project_id, id=resource_id)
        message = self.build_notification_message(
            self.admin_account.user_id, self.event_resized, payload,
            timestamp=end_time)
        handle = floatingip.FloatingIpResizeEnd()
        handle.process_notification(message)

        price = pricing.calculate_price(quantity, product.unit_price)
        order = self.dbconn.get_order(self.admin_req_context, order.order_id)
        self.assertDecimalEqual(price, order.unit_price)
        subs_list = list(self.dbconn.get_subscriptions_by_order_id(
            self.admin_req_context, order.order_id))
        self.assertEqual(1, len(subs_list))
        for subs in subs_list:
            self.assertEqual(quantity, subs.quantity)

        bill1 = self.dbconn.get_bill(self.admin_req_context, bill1.bill_id)
        self.assertEqual(self.datetime_to_str(end_time),
                         self.datetime_to_str(bill1.end_time))
        bill2 = self.dbconn.get_latest_bill(self.admin_req_context,
                                            order.order_id)
        self.assertEqual(self.datetime_to_str(end_time),
                         self.datetime_to_str(bill2.start_time))
        self.assertDecimalEqual(price, bill2.unit_price)

    def test_floatingip_delete_end(self):
        project_id = self.admin_account.project_id
        end_time = self.utcnow()
        start_time = end_time - datetime.timedelta(hours=1)

        rate_limit = 1024
        resource_id = self.create_floatingip(
            rate_limit, project_id, timestamp=start_time)
        order = self.dbconn.get_order_by_resource_id(
            self.admin_req_context, resource_id)

        payload = self.build_floatingip_payload(
            self.floating_ip_address, rate_limit,
            project_id, id=resource_id)
        payload['floatingip_id'] = resource_id
        message = self.build_notification_message(
            self.admin_account.user_id, self.event_deleted, payload,
            timestamp=end_time)
        handle = floatingip.FloatingIpDeleteEnd()
        handle.process_notification(message)

        order = self.dbconn.get_order(self.admin_req_context, order.order_id)
        self.assertEqual(gring_const.STATE_DELETED, order.status)
        bill = self.dbconn.get_latest_bill(self.admin_req_context,
                                           order.order_id)
        self.assertDecimalEqual('0', bill.unit_price)

    def test_floatingip_get_unit_price(self):
        product = self.product_fixture.ip_products[0]
        rate_limit = 10240
        quantity = pricing.rate_limit_to_unit(rate_limit)
        expected_price = pricing.calculate_price(quantity, product.unit_price)

        payload = self.build_floatingip_payload(
            self.floating_ip_address, rate_limit,
            self.admin_account.project_id)
        message = self.build_notification_message(
            self.admin_account.user_id, self.event_created, payload)

        handle = floatingip.FloatingIpCreateEnd()
        price = handle.get_unit_price(message,
                                      gring_const.STATE_RUNNING)
        self.assertDecimalEqual(expected_price, price)

    def test_floatingip_change_unit_price(self):
        product = self.product_fixture.ip_products[0]
        project_id = self.admin_account.project_id
        end_time = self.utcnow()
        start_time = end_time - datetime.timedelta(hours=1)

        # rate_limit = 1024
        rate_limit = 1024
        resource_id = self.create_floatingip(
            rate_limit, project_id, timestamp=start_time)
        order = self.dbconn.get_order_by_resource_id(
            self.admin_req_context, resource_id)

        # change rate_limit to 1024 * 11
        rate_limit = 1024 * 11
        quantity = pricing.rate_limit_to_unit(rate_limit)
        expected_price = pricing.calculate_price(quantity, product.unit_price)
        payload = self.build_floatingip_payload(
            self.floating_ip_address, rate_limit, project_id, id=resource_id)
        message = self.build_notification_message(
            self.admin_account.user_id, self.event_resized, payload,
            timestamp=end_time)
        handle = floatingip.FloatingIpCreateEnd()
        handle.change_unit_price(
            message, gring_const.STATE_RUNNING, order.order_id)
        order = self.dbconn.get_order(self.admin_req_context, order.order_id)
        self.assertEqual(expected_price, order.unit_price)
        subs_list = list(self.dbconn.get_subscriptions_by_order_id(
            self.admin_req_context, order.order_id))
        for subs in subs_list:
            self.assertEqual(quantity, subs.quantity)


class FloatingIpSetTestCase(test_service.WaiterServiceTestCase):

    def setUp(self):
        super(FloatingIpSetTestCase, self).setUp()

        self.event_created = floatingip.EVENT_FLOATINGIPSET_CREATE_END
        self.event_resized = floatingip.EVENT_FLOATINGIPSET_RESIZE_END
        self.event_deleted = floatingip.EVENT_FLOATINGIPSET_DELETE_END

        self.fipset = {
            'CHINAUNICOM': ['2.4.6.8'],
            'CHINAMOBILE': ['1.2.3.4'],
        }

        self.useFixture(mockpatch.PatchObject(
            floatingip.FloatingIpNotificationBase,
            '_send_email_notification'))

        self.product = self.product_fixture.ip_products[1]

    def create_floatingipset(self, rate_limit, project_id, timestamp=None):
        handle = floatingip.FloatingIpCreateEnd()
        payload = self.build_floatingipset_payload(
            self.fipset, rate_limit, project_id)
        resource_id = payload['floatingipset']['id']
        message = self.build_notification_message(
            self.admin_account.user_id, self.event_created, payload,
            timestamp=timestamp)
        handle.process_notification(message)
        return resource_id

    def test_floatingipset_create_end(self):
        rate_limit = 10240
        quantity = pricing.rate_limit_to_unit(rate_limit)
        price = pricing.calculate_price(quantity, self.product.unit_price)
        project_id = self.admin_account.project_id
        start_time = self.utcnow()

        resource_id = self.create_floatingipset(
            rate_limit, project_id, timestamp=start_time)

        order = self.dbconn.get_order_by_resource_id(
            self.admin_req_context, resource_id)
        self.assertDecimalEqual(price, order.unit_price)
        subs_list = list(self.dbconn.get_subscriptions_by_order_id(
            self.admin_req_context, order.order_id))
        self.assertEqual(1, len(subs_list))
        for subs in subs_list:
            self.assertEqual(gring_const.STATE_RUNNING, subs.type)
            self.assertEqual(quantity, subs.quantity)

        bill = self.dbconn.get_latest_bill(self.admin_req_context,
                                           order.order_id)
        self.assertEqual(resource_id, bill.resource_id)
        self.assertEqual(self.datetime_to_str(start_time),
                         self.datetime_to_str(bill.start_time))
        self.assertDecimalEqual(price, bill.unit_price)

    def test_floatingipset_resize_end(self):
        project_id = self.admin_account.project_id
        end_time = self.utcnow()
        start_time = end_time - datetime.timedelta(hours=1)

        # rate_limit = 1024
        rate_limit = 1024
        resource_id = self.create_floatingipset(
            rate_limit, project_id, timestamp=start_time)
        order = self.dbconn.get_order_by_resource_id(
            self.admin_req_context, resource_id)
        bill1 = self.dbconn.get_latest_bill(self.admin_req_context,
                                            order.order_id)

        # change rate_limit to 1024 * 11
        rate_limit = 1024 * 11
        quantity = pricing.rate_limit_to_unit(rate_limit)
        payload = self.build_floatingipset_payload(
            self.fipset, rate_limit, project_id, id=resource_id)
        message = self.build_notification_message(
            self.admin_account.user_id, self.event_resized, payload,
            timestamp=end_time)
        handle = floatingip.FloatingIpResizeEnd()
        handle.process_notification(message)

        price = pricing.calculate_price(quantity, self.product.unit_price)
        order = self.dbconn.get_order(self.admin_req_context, order.order_id)
        self.assertDecimalEqual(price, order.unit_price)
        subs_list = list(self.dbconn.get_subscriptions_by_order_id(
            self.admin_req_context, order.order_id))
        self.assertEqual(1, len(subs_list))
        for subs in subs_list:
            self.assertEqual(quantity, subs.quantity)

        bill1 = self.dbconn.get_bill(self.admin_req_context, bill1.bill_id)
        self.assertEqual(self.datetime_to_str(end_time),
                         self.datetime_to_str(bill1.end_time))
        bill2 = self.dbconn.get_latest_bill(self.admin_req_context,
                                            order.order_id)
        self.assertEqual(self.datetime_to_str(end_time),
                         self.datetime_to_str(bill2.start_time))
        self.assertDecimalEqual(price, bill2.unit_price)

    def test_floatingipset_delete_end(self):
        project_id = self.admin_account.project_id
        end_time = self.utcnow()
        start_time = end_time - datetime.timedelta(hours=1)

        rate_limit = 1024
        resource_id = self.create_floatingipset(
            rate_limit, project_id, timestamp=start_time)
        order = self.dbconn.get_order_by_resource_id(
            self.admin_req_context, resource_id)

        payload = self.build_floatingipset_payload(
            self.fipset, rate_limit, project_id, id=resource_id)
        payload['floatingipset_id'] = resource_id
        message = self.build_notification_message(
            self.admin_account.project_id, self.event_deleted, payload,
            timestamp=end_time)
        handle = floatingip.FloatingIpDeleteEnd()
        handle.process_notification(message)

        order = self.dbconn.get_order(self.admin_req_context, order.order_id)
        self.assertEqual(gring_const.STATE_DELETED, order.status)
        bill = self.dbconn.get_latest_bill(self.admin_req_context,
                                           order.order_id)
        self.assertDecimalEqual('0', bill.unit_price)


class FloatingIpEmailNofiticationTestCase(test_service.WaiterServiceTestCase,
                                          test_utils.ServiceTestMixin):

    def setUp(self):
        super(FloatingIpEmailNofiticationTestCase, self).setUp()
        self.project_id = self.admin_account.project_id
        self.floating_ip_address = '1.2.3.4'
        self.fipset = {
            'CHINAUNICOM': ['2.4.6.8'],
            'CHINAMOBILE': ['1.2.3.4'],
        }
        self.rate_limit = 1024

        user_info = self.build_uos_user_info_from_keystone(
            user_id=self.admin_account.user_id, name='admin')
        self.useFixture(mockpatch.PatchObject(
            keystone, 'get_uos_user', mock.Mock(return_value=user_info)))
        self.mocked_lotus_method = mock.MagicMock(name='lotus')
        self.useFixture(mockpatch.PatchObject(
            lotus, 'send_notification_email', self.mocked_lotus_method))
        self.product = self.product_fixture.ip_products[1]

    def create_floatingip(self, timestamp=None):
        handle = floatingip.FloatingIpCreateEnd()
        payload = self.build_floatingip_payload(
            self.floating_ip_address, self.rate_limit, self.project_id)
        resource_id = payload['floatingip']['id']
        message = self.build_notification_message(
            self.admin_account.user_id,
            floatingip.EVENT_FLOATINGIP_CREATE_END, payload,
            timestamp=timestamp)
        handle.process_notification(message)
        return resource_id, message

    def create_floatingipset(self, timestamp=None):
        handle = floatingip.FloatingIpCreateEnd()
        payload = self.build_floatingipset_payload(
            self.fipset, self.rate_limit, self.project_id)
        resource_id = payload['floatingipset']['id']
        message = self.build_notification_message(
            self.admin_account.user_id,
            floatingip.EVENT_FLOATINGIPSET_CREATE_END,
            payload, timestamp=timestamp)
        handle.process_notification(message)
        return resource_id, message

    def test_floatingip_create_end_send_email(self):
        _unused, message = self.create_floatingip()
        ip_str = floatingip.generate_ip_str(message)
        self.assertEqual(True, self.mocked_lotus_method.called)
        call_args = self.mocked_lotus_method.call_args[0]
        self.assertIn(ip_str, call_args[1])

    def test_floatingip_create_end_send_email_failed(self):
        with mock.patch.object(
                floatingip.FloatingIpNotificationBase,
                '_send_email_notification') as mocked_method:
            mocked_method.side_effect = Exception
            self.create_floatingip()

    def test_floatingip_delete_end_send_email(self):
        end_time = self.utcnow()
        start_time = end_time - datetime.timedelta(hours=1)

        resource_id, _unused = self.create_floatingip(timestamp=start_time)

        payload = self.build_floatingip_payload(
            self.floating_ip_address, self.rate_limit,
            self.project_id, id=resource_id)
        payload['floatingip_id'] = resource_id
        message = self.build_notification_message(
            self.admin_account.user_id,
            floatingip.EVENT_FLOATINGIP_DELETE_END,
            payload, timestamp=end_time)
        handle = floatingip.FloatingIpDeleteEnd()
        handle.process_notification(message)

        ip_str = floatingip.generate_ip_str(message)
        self.assertEqual(2, self.mocked_lotus_method.call_count)
        call_args = self.mocked_lotus_method.call_args[0]
        self.assertIn(ip_str, call_args[1])

    def test_floatingip_delete_end_send_email_failed(self):
        end_time = self.utcnow()
        start_time = end_time - datetime.timedelta(hours=1)

        resource_id, _unused = self.create_floatingip(timestamp=start_time)

        payload = self.build_floatingip_payload(
            self.floating_ip_address, self.rate_limit,
            self.project_id, id=resource_id)
        payload['floatingip_id'] = resource_id
        message = self.build_notification_message(
            self.admin_account.user_id,
            floatingip.EVENT_FLOATINGIP_DELETE_END,
            payload, timestamp=end_time)
        with mock.patch.object(
                floatingip.FloatingIpNotificationBase,
                '_send_email_notification') as mocked_method:
            mocked_method.side_effect = Exception
            handle = floatingip.FloatingIpDeleteEnd()
            handle.process_notification(message)

    def test_floatingipset_create_end_send_email(self):
        _unused, message = self.create_floatingipset()
        ip_str = floatingip.generate_ip_str(message)
        self.assertEqual(True, self.mocked_lotus_method.called)
        call_args = self.mocked_lotus_method.call_args[0]
        self.assertIn(ip_str, call_args[1])

    def test_floatingipset_delete_end_send_email(self):
        end_time = self.utcnow()
        start_time = end_time - datetime.timedelta(hours=1)

        resource_id, _unused = self.create_floatingipset(timestamp=start_time)

        payload = self.build_floatingipset_payload(
            self.fipset, self.rate_limit, self.project_id, id=resource_id)
        payload['floatingipset_id'] = resource_id
        message = self.build_notification_message(
            self.admin_account.project_id,
            floatingip.EVENT_FLOATINGIPSET_DELETE_END,
            payload, timestamp=end_time)
        handle = floatingip.FloatingIpDeleteEnd()
        handle.process_notification(message)

        ip_str = floatingip.generate_ip_str(message)
        self.assertEqual(2, self.mocked_lotus_method.call_count)
        call_args = self.mocked_lotus_method.call_args[0]
        self.assertIn(ip_str, call_args[1])
