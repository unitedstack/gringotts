
import datetime

from oslo_config import cfg

from gringotts import constants as gring_const
from gringotts.openstack.common import jsonutils
from gringotts.openstack.common import log as logging
from gringotts.price import pricing
from gringotts.services import cinder
from gringotts.tests import service as test_service
from gringotts.waiter.plugins import volume

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class VolumeTestCase(test_service.WaiterServiceTestCase):

    def setUp(self):
        super(VolumeTestCase, self).setUp()

        self.event_created = 'volume.created.end'
        self.event_resized = 'volume.resized.end'
        self.event_deleted = 'volume.deleted.end'

        self.price_data = self.build_segmented_price_data(
            '5.0000', [[80, 0.1], [30, 0.2], [10, 0.3]])

        self.project_id = self.admin_account.project_id
        self.user_id = self.admin_account.user_id

        self.sata_volume = self.product_fixture.volume_products[0]
        self.ssd_volume = self.product_fixture.volume_products[1]

        self.size = 15
        self.new_size = 35

    def _get_product_by_volume_type(self, volume_type=None):
        if volume_type and volume_type == 'sata':
            return self.sata_volume

        return self.ssd_volume

    def _set_product_volume_to_segmented_price(self, volume_type=None):
        extra = {'price': self.price_data}
        product = self._get_product_by_volume_type(volume_type)

        return self.update_product_in_db(product.product_id, extra=extra)

    def _create_volume(self, volume_type, size, project_id, timestamp=None):
        payload = self.build_volume_payload(volume_type, size, project_id)
        resource_id = payload['volume_id']

        message = self.build_notification_message(
            self.user_id, self.event_created,
            payload, timestamp=timestamp)
        handle = volume.VolumeCreateEnd()
        handle.process_notification(message)

        return resource_id

    def _test_volume_create_end(self, volume_type=None):
        product = self._get_product_by_volume_type(volume_type)
        price = pricing.calculate_price(self.size, product.unit_price)
        start_time = self.utcnow()

        resource_id = self._create_volume(
            volume_type, self.size, self.project_id,
            timestamp=start_time
        )
        order = self.dbconn.get_order_by_resource_id(
            self.admin_req_context, resource_id)
        self.assertDecimalEqual(price, order.unit_price)

        subs_list = list(self.dbconn.get_subscriptions_by_order_id(
            self.admin_req_context, order.order_id))
        self.assertEqual(1, len(subs_list))
        for subs in subs_list:
            self.assertEqual(gring_const.STATE_RUNNING, subs.type)
            self.assertEqual(self.size, subs.quantity)
            subs_product = self.dbconn.get_product(
                self.admin_req_context,
                subs.product_id
            )
            self.assertEqual(product.name, subs_product.name)

        bill = self.dbconn.get_latest_bill(self.admin_req_context,
                                           order.order_id)
        self.assertEqual(resource_id, bill.resource_id)
        self.assertEqual(self.datetime_to_str(start_time),
                         self.datetime_to_str(bill.start_time))
        self.assertDecimalEqual(price, bill.unit_price)

    def _test_volume_create_unit_price(self, size, volume_type=None,
                                       is_segmented_price=False):
        if is_segmented_price:
            product = self._set_product_volume_to_segmented_price(volume_type)
            extra = jsonutils.loads(product.extra)
            price = pricing.calculate_price(size, product.unit_price,
                                            extra['price'])
        else:
            product = self._get_product_by_volume_type(volume_type)
            price = pricing.calculate_price(size, product.unit_price)

        resource_id = self._create_volume(volume_type, size, self.project_id)
        order = self.dbconn.get_order_by_resource_id(
            self.admin_req_context, resource_id)
        self.assertDecimalEqual(price, order.unit_price)

        bill = self.dbconn.get_latest_bill(
            self.admin_req_context, order.order_id)
        self.assertDecimalEqual(price, bill.unit_price)

    def _test_volume_resize_end(self, volume_type=None):
        product = self._get_product_by_volume_type(volume_type)
        end_time = self.utcnow()
        start_time = end_time - datetime.timedelta(hours=1)

        # original size
        resource_id = self._create_volume(
            volume_type, self.size, self.project_id,
            timestamp=start_time
        )
        order = self.dbconn.get_order_by_resource_id(
            self.admin_req_context, resource_id)
        bill1 = self.dbconn.get_latest_bill(self.admin_req_context,
                                            order.order_id)

        # change to new size
        payload = self.build_volume_payload(
            volume_type, self.new_size, self.project_id,
            volume_id=resource_id
        )
        message = self.build_notification_message(
            self.user_id,
            self.event_resized, payload,
            timestamp=end_time
        )
        handle = volume.VolumeResizeEnd()
        handle.process_notification(message)

        price = pricing.calculate_price(self.new_size, product.unit_price)
        order = self.dbconn.get_order(self.admin_req_context, order.order_id)
        self.assertDecimalEqual(price, order.unit_price)

        subs_list = list(self.dbconn.get_subscriptions_by_order_id(
            self.admin_req_context, order.order_id))
        self.assertEqual(1, len(subs_list))
        for subs in subs_list:
            self.assertEqual(self.new_size, subs.quantity)

        bill1 = self.dbconn.get_bill(self.admin_req_context, bill1.bill_id)
        self.assertEqual(self.datetime_to_str(end_time),
                         self.datetime_to_str(bill1.end_time))
        bill2 = self.dbconn.get_latest_bill(self.admin_req_context,
                                            order.order_id)
        self.assertEqual(self.datetime_to_str(end_time),
                         self.datetime_to_str(bill2.start_time))
        self.assertDecimalEqual(price, bill2.unit_price)

    def _test_volume_delete_end(self, volume_type=None):
        end_time = self.utcnow()
        start_time = end_time - datetime.timedelta(hours=1)

        resource_id = self._create_volume(
            volume_type, self.size, self.project_id,
            timestamp=start_time
        )
        order = self.dbconn.get_order_by_resource_id(
            self.admin_req_context, resource_id)

        payload = self.build_volume_payload(
            volume_type, self.size, self.project_id,
            volume_id=resource_id
        )
        message = self.build_notification_message(
            self.user_id,
            self.event_deleted, payload,
            timestamp=end_time
        )
        handle = volume.VolumeDeleteEnd()
        handle.process_notification(message)

        order = self.dbconn.get_order(self.admin_req_context, order.order_id)
        self.assertEqual(gring_const.STATE_DELETED, order.status)

        bill = self.dbconn.get_latest_bill(
            self.admin_req_context, order.order_id)
        self.assertDecimalEqual('0', bill.unit_price)

    def _test_volume_get_unit_price(self, volume_type=None):
        product = self._get_product_by_volume_type(volume_type)
        expected_price = pricing.calculate_price(self.size, product.unit_price)

        payload = self.build_volume_payload(volume_type, self.size,
                                            self.project_id)
        message = self.build_notification_message(
            self.user_id,
            self.event_created, payload
        )
        handle = volume.VolumeCreateEnd()

        price = handle.get_unit_price(message, gring_const.STATE_RUNNING)
        self.assertDecimalEqual(expected_price, price)

    def _test_volume_change_unit_price(self, volume_type=None):
        product = self._get_product_by_volume_type(volume_type)
        end_time = self.utcnow()
        start_time = end_time - datetime.timedelta(hours=1)

        # original size
        resource_id = self._create_volume(
            volume_type, self.size, self.project_id,
            timestamp=start_time
        )
        order = self.dbconn.get_order_by_resource_id(
            self.admin_req_context,
            resource_id
        )

        # change to new size
        expected_price = pricing.calculate_price(self.new_size,
                                                 product.unit_price)
        payload = self.build_volume_payload(
            volume_type, self.new_size, self.project_id,
            volume_id=resource_id
        )
        message = self.build_notification_message(
            self.user_id, self.event_resized,
            payload, timestamp=end_time
        )

        # change_unit_price()
        handle = volume.VolumeCreateEnd()
        handle.change_unit_price(
            message, gring_const.STATE_RUNNING,
            order.order_id
        )

        order = self.dbconn.get_order(self.admin_req_context, order.order_id)
        self.assertDecimalEqual(expected_price, order.unit_price)

        subs_list = list(self.dbconn.get_subscriptions_by_order_id(
            self.admin_req_context, order.order_id))
        for subs in subs_list:
            self.assertEqual(self.new_size, subs.quantity)

    def _test_volume_get_unit_price_with_again_event(self, volume_type=None):
        product = self._get_product_by_volume_type(volume_type)
        expected_price = pricing.calculate_price(self.size, product.unit_price)

        payload = self.build_volume_payload(
            volume_type, self.size, self.project_id)
        vol = cinder.Volume(
            id=payload['volume_id'], name=payload['display_name'],
            resource_type='volume',
            size=payload['size'], type=payload['volume_type'],
            project_id=payload['tenant_id'], user_id=payload['user_id']
        )
        message = vol.to_message()
        handle = volume.VolumeCreateEnd()

        price = handle.get_unit_price(message,
                                      gring_const.STATE_RUNNING)
        self.assertDecimalEqual(expected_price, price)

    def _test_volume_change_unit_price_with_again_event(self,
                                                        volume_type=None):
        product = self._get_product_by_volume_type(volume_type)
        end_time = self.utcnow()
        start_time = end_time - datetime.timedelta(hours=1)

        # original size
        resource_id = self._create_volume(
            volume_type, self.size, self.project_id,
            timestamp=start_time
        )
        order = self.dbconn.get_order_by_resource_id(
            self.admin_req_context, resource_id)

        # change to new size
        expected_price = pricing.calculate_price(self.new_size,
                                                 product.unit_price)
        payload = self.build_volume_payload(
            volume_type, self.new_size, self.project_id,
            volume_id=resource_id
        )
        vol = cinder.Volume(
            id=payload['volume_id'], name=payload['display_name'],
            resource_type='volume',
            size=payload['size'], type=payload['volume_type'],
            project_id=payload['tenant_id'], user_id=payload['user_id']
        )
        message = vol.to_message()
        handle = volume.VolumeCreateEnd()
        handle.change_unit_price(
            message, gring_const.STATE_RUNNING, order.order_id)

        order = self.dbconn.get_order(self.admin_req_context, order.order_id)
        self.assertDecimalEqual(expected_price, order.unit_price)

        subs_list = list(self.dbconn.get_subscriptions_by_order_id(
            self.admin_req_context, order.order_id))
        for subs in subs_list:
            self.assertEqual(self.new_size, subs.quantity)

    def test_volume_create_end(self):
        self._test_volume_create_end()
        self._test_volume_create_end('sata')
        self._test_volume_create_end('ssd')

    def test_volume_create_end_unit_price(self):
        for size in [10, 30, 80]:
            self._test_volume_create_unit_price(size, 'sata')
            self._test_volume_create_unit_price(size, 'ssd')
            self._test_volume_create_unit_price(size)

    def test_volume_create_and_segmented_price(self):
        for size in [15, 35, 85]:
            self._test_volume_create_unit_price(size, 'sata', True)
            self._test_volume_create_unit_price(size, 'ssd', True)
            self._test_volume_create_unit_price(size, is_segmented_price=True)

    def test_volume_resize_end(self):
        self._test_volume_resize_end()
        self._test_volume_resize_end('sata')
        self._test_volume_resize_end('ssd')

    def test_volume_delete_end(self):
        self._test_volume_delete_end()
        self._test_volume_delete_end('sata')
        self._test_volume_delete_end('ssd')

    def test_volume_get_unit_price(self):
        self._test_volume_get_unit_price()
        self._test_volume_get_unit_price('sata')
        self._test_volume_get_unit_price('ssd')

    def test_volume_change_unit_price(self):
        self._test_volume_change_unit_price()
        self._test_volume_change_unit_price('sata')
        self._test_volume_change_unit_price('ssd')

    def test_volume_get_unit_price_with_again_event(self):
        self._test_volume_get_unit_price_with_again_event()
        self._test_volume_get_unit_price_with_again_event('sata')
        self._test_volume_get_unit_price_with_again_event('ssd')

    def test_volume_change_unit_price_with_again_event(self):
        self._test_volume_change_unit_price_with_again_event()
        self._test_volume_change_unit_price_with_again_event('sata')
        self._test_volume_change_unit_price_with_again_event('ssd')
