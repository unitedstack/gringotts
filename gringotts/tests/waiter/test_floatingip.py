
from oslo_config import cfg

from gringotts import constants as gring_const
from gringotts.openstack.common import log as logging
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

    def test_floatingip_created(self):
        floating_ip_address = '2.4.6.8'
        rate_limit = 1024
        project_id = self.admin_account.project_id
        payload = self.build_floatingip_payload(floating_ip_address,
                                                rate_limit, project_id)
        resource_id = payload['floatingip']['id']
        message = self.build_notification_message(
            self.event_created, payload, self.publisher_id)

        handle = floatingip.FloatingIpCreateEnd()
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
