
from gringotts import constants as gring_const
from gringotts.openstack.common import log as logging
from gringotts.tests import rest

LOG = logging.getLogger(__name__)


class SubscriptionTestCase(rest.RestfulTestCase):

    def setUp(self):
        super(SubscriptionTestCase, self).setUp()

        self.subs_path = '/v2/subs'

        self.admin_headers = self.build_admin_http_headers()

    def test_create_subs(self):
        product = self.product_fixture.instance_products[0]
        resource_volume = 1
        order_id = self.new_order_id()
        user_id = self.admin_account.user_id
        project_id = self.admin_account.project_id

        running_subs_ref = self.new_subs_ref(
            product.service, product.name, resource_volume,
            gring_const.STATE_RUNNING, order_id, project_id, user_id
        )
        suspend_subs_ref = self.new_subs_ref(
            product.service, product.name, resource_volume,
            gring_const.STATE_SUSPEND, order_id, project_id, user_id
        )
        stopped_subs_ref = self.new_subs_ref(
            product.service, product.name, resource_volume,
            gring_const.STATE_STOPPED, order_id, project_id, user_id
        )
        subs_ref_list = [
            running_subs_ref, suspend_subs_ref, stopped_subs_ref
        ]

        for subs_ref in subs_ref_list:
            self.post(self.subs_path, headers=self.admin_headers,
                      body=subs_ref, expected_status=200)
            subs_ref['product_id'] = product.product_id

        subs_list = list(self.dbconn.get_subscriptions_by_order_id(
            self.admin_req_context, order_id)
        )
        self.assertInSubsList(running_subs_ref, subs_list)
        self.assertInSubsList(suspend_subs_ref, subs_list)
        self.assertInSubsList(stopped_subs_ref, subs_list)

    def test_create_subs_with_nonexist_product_failed(self):
        product = self.product_fixture.instance_products[0]
        subs_ref = self.new_subs_ref(
            product.service, self.new_uuid(), 1,
            gring_const.STATE_RUNNING, self.new_order_id(),
            self.admin_account.project_id, self.admin_account.user_id
        )
        # TODO(liuchenhong): This API should return 4xx when
        # create subscriptions failed, rather than 200
        self.post(self.subs_path, headers=self.admin_headers,
                  body=subs_ref, expected_status=200)

    def test_update_subs_quantity(self):
        product = self.product_fixture.instance_products[0]
        resource_volume = 1
        order_id = self.new_order_id()
        user_id = self.admin_account.user_id
        project_id = self.admin_account.project_id

        subs = self.create_subs_in_db(
            product, resource_volume, gring_const.STATE_RUNNING,
            order_id, project_id, user_id
        )

        new_subs_ref = {
            'order_id': subs.order_id,
            'quantity': 10,
            'change_to': subs.type,
            'service': product.service,
            'region_id': subs.region_id,
        }
        self.put(self.subs_path, headers=self.admin_headers,
                 body=new_subs_ref)
        new_subs_ref['product_id'] = product.product_id
        new_subs_ref['user_id'] = user_id
        new_subs_ref['project_id'] = project_id

        subs_list = list(self.dbconn.get_subscriptions_by_order_id(
            self.admin_req_context, order_id))
        self.assertEqual(1, len(subs_list))
        subs = subs_list[0]
        self.assertSubsEqual(new_subs_ref, subs.as_dict())
        self.assertEqual(new_subs_ref['quantity'], subs.quantity)

    def test_update_subs_flavor(self):
        product1 = self.product_fixture.instance_products[0]
        product2 = self.product_fixture.instance_products[1]
        resource_volume = 1
        order_id = self.new_order_id()
        user_id = self.admin_account.user_id
        project_id = self.admin_account.project_id

        subs = self.create_subs_in_db(
            product1, resource_volume, gring_const.STATE_RUNNING,
            order_id, project_id, user_id
        )

        new_subs_ref = {
            'order_id': subs.order_id,
            'change_to': subs.type,
            'old_flavor': product1.name,
            'new_flavor': product2.name,
            'service': product1.service,
            'region_id': subs.region_id,
        }
        self.put(self.subs_path, headers=self.admin_headers,
                 body=new_subs_ref)
        new_subs_ref['product_id'] = product2.product_id
        new_subs_ref['user_id'] = user_id
        new_subs_ref['project_id'] = project_id

        subs_list = list(self.dbconn.get_subscriptions_by_order_id(
            self.admin_req_context, order_id))
        self.assertEqual(1, len(subs_list))
        subs = subs_list[0]
        self.assertSubsEqual(new_subs_ref, subs.as_dict())
        self.assertEqual(product2.unit_price, subs.unit_price)
