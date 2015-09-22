
import datetime

from oslo_config import cfg

from gringotts import constants as gring_const
from gringotts.openstack.common import log as logging
from gringotts.openstack.common import timeutils
from gringotts.tests import rest

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class BillTestCase(rest.RestfulTestCase):

    def setUp(self):
        super(BillTestCase, self).setUp()
        self.config_fixture.config(enable=False, group='external_billing')

        self.bill_path = '/v2/bills'
        self.headers = self.build_admin_http_headers()

    def test_create_bill(self):
        product = self.product_fixture.instance_products[0]
        resource_volume = 1
        resource_type = gring_const.RESOURCE_INSTANCE
        order_id = self.new_order_id()
        user_id = self.admin_account.user_id
        project_id = self.admin_account.project_id

        subs = self.create_subs_in_db(
            product, resource_volume, gring_const.STATE_RUNNING,
            order_id, project_id, user_id,
        )
        order = self.create_order_in_db(
            float(self.quantize(subs.unit_price)) * resource_volume,
            subs.unit, user_id, project_id,
            resource_type, subs.type, order_id=order_id
        )

        action_time = self.utcnow()
        bill_ref = self.new_bill_ref(order.order_id,
                                     self.datetime_to_str(action_time))
        resp = self.post(self.bill_path, headers=self.headers,
                         body=bill_ref, expected_status=200)
        bill_result = resp.json_body
        bill_ref.update({
            'user_id': user_id,
            'project_id': project_id,
            'region_id': order.region_id,
            'resource_id': order.resource_id,
        })
        self.assertNotEqual('-1', bill_result['type'])
        self.assertBillResultEqual(bill_ref, bill_result)

        bill = self.dbconn.get_latest_bill(self.admin_req_context,
                                           order.order_id)
        self.assertBillMatchOrder(bill.as_dict(), order.as_dict())
        self.assertPriceEqual(bill.total_price, order.unit_price)
        self.assertEqual(gring_const.BILL_PAYED, bill.status)

        end_time = bill.end_time
        self.assertEqual((end_time - action_time),
                         datetime.timedelta(hours=1))

    def test_close_bill(self):
        self.bill_path = '/v2/bills/close'
        product = self.product_fixture.instance_products[0]
        resource_volume = 1
        resource_type = gring_const.RESOURCE_INSTANCE
        order_id = self.new_order_id()
        user_id = self.admin_account.user_id
        project_id = self.admin_account.project_id

        subs = self.create_subs_in_db(
            product, resource_volume, gring_const.STATE_RUNNING,
            order_id, project_id, user_id,
        )
        order = self.create_order_in_db(
            float(self.quantize(subs.unit_price)), subs.unit, user_id,
            project_id, resource_type, subs.type, order_id=order_id
        )

        start_time = self.utcnow()
        self.dbconn.create_bill(self.admin_req_context, order.order_id,
                                action_time=start_time)

        bill = self.dbconn.get_latest_bill(self.admin_req_context,
                                           order.order_id)
        self.assertBillMatchOrder(bill.as_dict(), order.as_dict())

        timedelta = datetime.timedelta(hours=0.5)
        end_time = start_time + timedelta
        bill_ref = self.new_bill_ref(order.order_id,
                                     self.datetime_to_str(end_time))
        resp = self.put(self.bill_path, headers=self.headers,
                        body=bill_ref, expected_status=200)
        bill_result = resp.json_body
        bill_ref.update({
            'user_id': user_id,
            'project_id': project_id,
            'region_id': order.region_id,
            'resource_id': order.resource_id,
        })
        self.assertNotEqual('-1', bill_result['type'])
        self.assertBillResultEqual(bill_ref, bill_result)

        # now order.status is changing
        order = self.dbconn.get_order(self.admin_req_context, order_id)
        self.assertEqual(gring_const.STATE_CHANGING, order.status)

        # calculate consumption
        total_price = self.quantize(
            float(order.unit_price) * (
                timeutils.delta_seconds(start_time, end_time) / 3600.0
            )
        )

        bill = self.dbconn.get_latest_bill(self.admin_req_context,
                                           order.order_id)
        self.assertBillMatchOrder(bill.as_dict(), order.as_dict())
        self.assertEqual(end_time, bill.end_time)
        self.assertEqual(gring_const.BILL_PAYED, bill.status)
        self.assertPriceEqual(total_price, bill.total_price)

    def test_update_bill(self):
        self.bill_path = '/v2/bills/update'
        product = self.product_fixture.instance_products[0]
        resource_volume = 1
        resource_type = gring_const.RESOURCE_INSTANCE
        order_id = self.new_order_id()
        user_id = self.admin_account.user_id
        project_id = self.admin_account.project_id

        subs = self.create_subs_in_db(
            product, resource_volume, gring_const.STATE_RUNNING,
            order_id, project_id, user_id,
        )
        order = self.create_order_in_db(
            float(self.quantize(subs.unit_price)), subs.unit, user_id,
            project_id, resource_type, subs.type, order_id=order_id
        )

        start_time = self.utcnow()
        self.dbconn.create_bill(self.admin_req_context, order.order_id,
                                action_time=start_time)

        bill = self.dbconn.get_latest_bill(self.admin_req_context,
                                           order.order_id)
        self.assertBillMatchOrder(bill.as_dict(), order.as_dict())

        timedelta = datetime.timedelta(hours=1)
        end_time = start_time + timedelta
        bill_ref = self.new_bill_ref(order.order_id)
        resp = self.put(self.bill_path, headers=self.headers,
                        body=bill_ref, expected_status=200)
        bill_result = resp.json_body
        bill_ref.update({
            'user_id': user_id,
            'project_id': project_id,
            'region_id': order.region_id,
            'resource_id': order.resource_id,
        })
        self.assertNotEqual('-1', bill_result['type'])
        self.assertBillResultEqual(bill_ref, bill_result)

        order = self.dbconn.get_order(self.admin_req_context, order_id)

        # calculate consumption
        total_price = self.quantize(
            float(order.unit_price) * (
                timeutils.delta_seconds(start_time, end_time) / 3600.0
            )
        )

        bill = self.dbconn.get_latest_bill(self.admin_req_context,
                                           order.order_id)
        self.assertBillMatchOrder(bill.as_dict(), order.as_dict())
        self.assertEqual(end_time, bill.end_time)
        self.assertEqual(gring_const.BILL_PAYED, bill.status)
        self.assertPriceEqual(total_price, bill.total_price)

    def test_get_bills(self):
        pass

    def test_get_bills_with_pagination(self):
        pass

    def test_get_bills_with_type(self):
        pass

    def test_get_bills_with_time_range(self):
        pass

    def test_get_bill_trends(self):
        pass

    def test_get_bill_detail_with_negative_limit_or_offset(self):
        path = "%s/%s" % (self.bill_path, 'detail')
        self.check_invalid_limit_or_offset(path)
