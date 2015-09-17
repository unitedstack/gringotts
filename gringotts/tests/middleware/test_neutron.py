
from oslo_config import cfg

from gringotts.middleware import neutron
from gringotts.openstack.common import log as logging
from gringotts.tests import core as tests

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class NeutronMiddlewareTestCase(tests.MiddlewareTestCase):

    def setUp(self):
        super(NeutronMiddlewareTestCase, self).setUp()

        self.app = self.load_middleware_app(neutron.filter_factory)

    def create_ok(self, path):
        owner_info = self.build_billing_owner(balance='1')
        self.mocked_client.get_billing_owner.return_value = owner_info
        self.post_json(path)

    def create_failed(self, path):
        owner_info = self.build_billing_owner()
        self.mocked_client.get_billing_owner.return_value = owner_info
        self.post_json(path, status=402)

    def test_create_floatingip(self):
        owner_info = self.build_billing_owner(
            balance=int(CONF.billing.min_balance_fip) + 1)
        self.mocked_client.get_billing_owner.return_value = owner_info
        self.post_json('/floatingips')

    def test_create_floatingip_without_enough_balance_failed(self):
        owner_info = self.build_billing_owner(
            balance=CONF.billing.min_balance_fip)
        self.mocked_client.get_billing_owner.return_value = owner_info
        self.post_json('/floatingips', status=402)

    def test_create_floatingip_with_owed_and_level9_account(self):
        owner_info = self.build_billing_owner(level=9, balance='-9.9')
        self.mocked_client.get_billing_owner.return_value = owner_info
        self.post_json('/floatingips')

    def test_update_floatingip_ratelimit(self):
        owner_info = self.build_billing_owner(balance='1')
        self.mocked_client.get_billing_owner.return_value = owner_info
        order = self.build_order(unit='hour')
        self.mocked_client.get_order_by_resource_id.return_value = order
        self.put_json('/uos_resources/%s/update_floatingip_ratelimit' % (
            self.new_uuid4()))

    def test_update_floatingip_ratelimit_without_enough_balance_failed(self):
        owner_info = self.build_billing_owner()
        self.mocked_client.get_billing_owner.return_value = owner_info
        order = self.build_order(unit='hour')
        self.mocked_client.get_order_by_resource_id.return_value = order
        self.put_json('/uos_resources/%s/update_floatingip_ratelimit' % (
            self.new_uuid4()), status=402)

    def test_create_fipset(self):
        owner_info = self.build_billing_owner(
            balance=(CONF.billing.min_balance_fip + '1'))
        self.mocked_client.get_billing_owner.return_value = owner_info
        self.post_json('/floatingipsets')

    def test_create_fipset_without_enough_balance_failed(self):
        owner_info = self.build_billing_owner(
            balance=CONF.billing.min_balance_fip)
        self.mocked_client.get_billing_owner.return_value = owner_info
        self.post_json('/floatingipsets', status=402)

    def test_create_fipset_with_owed_and_level9_account(self):
        owner_info = self.build_billing_owner(level=9, balance='-9.9')
        self.mocked_client.get_billing_owner.return_value = owner_info
        self.post_json('/floatingiipsets')

    def test_update_fipset_ratelimit(self):
        owner_info = self.build_billing_owner(balance='1')
        self.mocked_client.get_billing_owner.return_value = owner_info
        order = self.build_order(unit='hour')
        self.mocked_client.get_order_by_resource_id.return_value = order
        self.put_json('/uos_resources/%s/update_floatingipset_ratelimit' % (
            self.new_uuid4()))

    def test_update_fipset_ratelimit_without_enough_balance_failed(self):
        owner_info = self.build_billing_owner()
        self.mocked_client.get_billing_owner.return_value = owner_info
        order = self.build_order(unit='hour')
        self.mocked_client.get_order_by_resource_id.return_value = order
        self.put_json('/uos_resources/%s/update_floatingipset_ratelimit' % (
            self.new_uuid4()), status=402)

    def test_create_routers(self):
        self.create_ok('/routers')

    def test_create_routers_without_enough_balance_failed(self):
        self.create_failed('/routers')

    def test_create_lbaas(self):
        self.create_ok('/lbaas/listeners')

    def test_create_lbaas_without_enough_balance_failed(self):
        self.create_failed('/lbaas/listeners')

    def test_update_lbaas(self):
        owner_info = self.build_billing_owner(balance='1')
        self.mocked_client.get_billing_owner.return_value = owner_info
        order = self.build_order(unit='hour')
        self.mocked_client.get_order_by_resource_id.return_value = order
        body = {
            'listener': {
                'connection_limit': 10,
                'admin_state_up': True,
            }
        }
        self.put_json('/lbaas/listeners/%s' % (self.new_uuid4()), params=body)

    def test_update_lbaas_without_enough_balance_failed(self):
        owner_info = self.build_billing_owner()
        self.mocked_client.get_billing_owner.return_value = owner_info
        order = self.build_order(unit='hour')
        self.mocked_client.get_order_by_resource_id.return_value = order
        body = {
            'listener': {
                'connection_limit': 10,
                'admin_state_up': True,
            }
        }
        self.put_json('/lbaas/listeners/%s' % (self.new_uuid4()),
                      params=body, status=402)
