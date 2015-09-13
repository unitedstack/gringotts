
import mock

from gringotts import exception
from gringotts.openstack.common import log as logging
from gringotts.services import keystone
from gringotts.tests import gring_fixtures
from gringotts.tests import rest
from gringotts.worker import api as worker_api

LOG = logging.getLogger(__name__)


class AccountTestCase(rest.RestfulTestCase):

    def setUp(self):
        super(AccountTestCase, self).setUp()

        self.account_path = '/v2/accounts'
        self.account_detail_path = '/v2/accounts/detail'
        self.admin_headers = self.build_admin_http_headers()
        self.demo_headers = self.build_demo_http_headers()

    def load_account_sample_data(self):
        sales_account = self.useFixture(
            gring_fixtures.AccountAndProjectData(
                self.dbconn, self.admin_req_context,
                self.new_user_id(), self.new_project_id(),
                self.demo_domain_id, 3
            )
        )

        self.useFixture(
            gring_fixtures.AccountAndProjectData(
                self.dbconn, self.admin_req_context,
                self.new_user_id(), self.new_project_id(),
                self.demo_domain_id, 3,
                sales_id=sales_account.user_id
            )
        )

    def build_account_query_url(self, user_id, custom=None,
                                offset=None, limit=None):
        return self.build_query_url(self.account_path, user_id, custom)

    def test_get_all_accounts(self):
        resp = self.get(self.account_path, headers=self.admin_headers)
        self.assertEqual(2, resp.json_body['total_count'])
        self.assertEqual(2, len(resp.json_body['accounts']))

    def test_get_all_accounts_in_detail(self):
        self.load_account_sample_data()

        user_info = self.build_uos_user_info_from_keystone(
            user_id='test', name='test')
        with mock.patch.object(keystone, 'get_uos_user',
                               return_value=user_info):
            resp = self.get(self.account_detail_path,
                            headers=self.admin_headers)
        self.assertEqual(4, resp.json_body['total_count'])
        self.assertEqual(4, len(resp.json_body['accounts']))

        for account in resp.json_body['accounts']:
            self.assertTrue('user' in account)
            self.assertTrue('salesperson' in account)
            self.assertFalse('user_id' in account)
            self.assertFalse('sales_id' in account)
            self.assertTrue('price_per_day' in account)
            self.assertTrue('remaining_day' in account)

    def test_get_all_accounts_in_detail_no_user(self):
        with mock.patch.object(keystone, 'get_uos_user',
                               side_effect=exception.NotFound()):
            resp = self.get(self.account_detail_path,
                            headers=self.admin_headers)
        self.assertEqual(0, resp.json_body['total_count'])
        self.assertEqual(0, len(resp.json_body['accounts']))

    def test_get_account_by_user_id(self):
        admin_account = self.admin_account
        account_ref = self.new_account_ref(
            user_id=admin_account.user_id, project_id=admin_account.project_id,
            domain_id=admin_account.domain_id, level=admin_account.level,
            owed=admin_account.owed, balance=admin_account.balance,
            consumption=admin_account.balance)

        query_url = self.build_account_query_url(account_ref['user_id'])
        resp = self.get(query_url, headers=self.admin_headers)
        account = resp.json_body
        self.assertAccountEqual(account_ref, account)

    def test_create_account(self):
        new_user_id = self.new_uuid()
        account_ref = self.new_account_ref(
            new_user_id, self.demo_project_id, self.demo_domain_id,
            level=3, owed=False)
        self.post(self.account_path, headers=self.admin_headers,
                  body=account_ref, expected_status=204)

        account = self.dbconn.get_account(self.admin_req_context, new_user_id)
        self.assertAccountEqual(account.as_dict(), account_ref)

    def test_update_account_level(self):
        demo_account = self.demo_account
        new_level = 4
        body = {'level': new_level}  # demo's level is 3
        query_url = self.build_account_query_url(demo_account.user_id,
                                                 'level')
        resp = self.put(query_url, headers=self.admin_headers,
                        body=body, expected_status=200)
        account_ref = resp.json_body
        self.assertEqual(new_level, account_ref['level'])

    def test_demo_update_account_level_failed(self):
        demo_account = self.demo_account
        new_level = 4
        body = {'level': new_level}  # demo's level is 3
        query_url = self.build_account_query_url(demo_account.user_id,
                                                 'level')
        self.put(query_url, headers=self.demo_headers,
                 body=body, expected_status=403)

    def test_get_account_estimate(self):
        pass

    def test_get_account_estimate_per_day(self):
        pass

    def test_account_charge(self):
        pass

    def test_account_charge_with_negative_value_failed(self):
        pass

    def test_delete_account_by_admin(self):
        """only admin account can delete the account."""
        admin_account = self.admin_account
        query_url = self.build_account_query_url(admin_account.user_id)
        self.delete(query_url, headers=self.admin_headers)

    def test_delete_account_with_nonexistent_user_id(self):
        """delete a account with nonexistent user_id."""
        fake_user_id = self.new_uuid()
        query_url = self.build_account_query_url(fake_user_id)
        self.delete(query_url, headers=self.admin_headers, expected_status=404)

    def test_delete_account_by_demo(self):
        """account without admin previlege can't delete the account."""
        demo_account = self.demo_account
        query_url = self.build_account_query_url(demo_account.user_id)
        self.delete(query_url, headers=self.demo_headers, expected_status=403)


class ExternalAccountTestCase(rest.RestfulTestCase):

    def setUp(self):
        super(ExternalAccountTestCase, self).setUp()
        self.config_fixture.config(enable=True,
                                   group='external_billing')
        self.config_fixture.config(auth_plugin='sign',
                                   group='external_billing')

        self.account_path = '/v2/accounts'
        self.admin_headers = self.build_admin_http_headers()
        self.demo_headers = self.build_demo_http_headers()

    def build_account_query_url(self, user_id, custom=None,
                                offset=None, limit=None):
        return self.build_query_url(self.account_path, user_id, custom)

    def build_external_balance(self, money=None, code="0"):
        return {
            "data": [
                {
                    "money": money
                }
            ],
            "code": code,
            "total": "1",
            "message": "account balance"
        }

    def test_get_nonexist_external_account(self):
        user_id = self.new_user_id()
        query_url = self.build_account_query_url(user_id)
        resp = self.get(query_url, headers=self.admin_headers,
                        expected_status=404)
        faultstring = "Account %s not found" % user_id
        self.assertEqual(faultstring, resp.json_body['faultstring'])

    def test_get_external_account_by_user_id(self):
        balance = "10"
        external_balance = self.build_external_balance(money=balance)

        admin_account = self.admin_account
        account_ref = self.new_account_ref(
            user_id=admin_account.user_id, project_id=admin_account.project_id,
            domain_id=admin_account.domain_id, level=admin_account.level,
            owed=admin_account.owed, balance=balance,
            consumption=admin_account.balance)
        query_url = self.build_account_query_url(account_ref['user_id'])

        with mock.patch.object(worker_api.HTTPAPI, 'get_external_balance',
                               return_value=external_balance):
            resp = self.get(query_url, headers=self.admin_headers)
            account = resp.json_body
        self.assertAccountEqual(account_ref, account)

    def test_get_external_account_balance_failed(self):
        user_id = self.admin_account.user_id

        query_url = self.build_account_query_url(user_id)
        e = exception.GetExternalBalanceFailed(user_id=user_id)
        with mock.patch.object(worker_api.HTTPAPI, 'get_external_balance',
                               side_effect=e):
            resp = self.get(query_url, headers=self.admin_headers,
                            expected_status=500)

        faultstring = "Fail to get external balance of account %s" % user_id
        self.assertEqual(faultstring, resp.json_body['faultstring'])


class SalesPersonsTestCase(rest.RestfulTestCase):

    def setUp(self):
        super(SalesPersonsTestCase, self).setUp()

        self.account_path = '/v2/accounts'
        self.salespersons_path = '/v2/salespersons'
        self.admin_headers = self.build_admin_http_headers()
        self.demo_headers = self.build_demo_http_headers()

        self.sales_account = self.useFixture(
            gring_fixtures.AccountAndProjectData(
                self.dbconn, self.admin_req_context,
                self.new_user_id(), self.new_project_id(),
                self.demo_domain_id, 3
            )
        )
        self.sales_account_headers = self.build_http_headers(
            user_id=self.sales_account.user_id,
            project_id=self.sales_account.project_id,
            domain_id=self.sales_account.domain_id,
            roles='uos_sales'
        )
        self.sales_account2 = self.useFixture(
            gring_fixtures.AccountAndProjectData(
                self.dbconn, self.admin_req_context,
                self.new_user_id(), self.new_project_id(),
                self.demo_domain_id, 3
            )
        )
        self.sales_account2_headers = self.build_http_headers(
            user_id=self.sales_account2.user_id,
            project_id=self.sales_account2.project_id,
            domain_id=self.sales_account2.domain_id,
            roles='uos_sales'
        )
        self.sales_admin_account = self.useFixture(
            gring_fixtures.AccountAndProjectData(
                self.dbconn, self.admin_req_context,
                self.new_user_id(), self.new_project_id(),
                self.demo_domain_id, 3,
            )
        )
        self.sales_admin_account_headers = self.build_http_headers(
            user_id=self.sales_admin_account.user_id,
            project_id=self.sales_admin_account.project_id,
            domain_id=self.sales_admin_account.domain_id,
            roles='uos_sales_admin'
        )

        self.load_salesperson_accounts_sample_data()

    def load_salesperson_accounts_sample_data(self):
        self.customers_number = 6
        self.sales_customers = []
        for i in range(self.customers_number):
            account = self.useFixture(
                gring_fixtures.AccountAndProjectData(
                    self.dbconn, self.admin_req_context,
                    self.new_user_id(), self.new_project_id(),
                    self.demo_domain_id, 3,
                    balance=i, consumption=(i + 0.1),
                    sales_id=self.sales_account.user_id
                )
            )
            account.name = account.user_id
            account.email = '%s@example.com' % account.name
            self.sales_customers.append(account)

    def get_account_from_list(self, user_id, account_list):
        for account in account_list:
            if user_id == account.user_id:
                return account
        else:
            return None

    def build_account_query_url(self, user_id, custom=None):
        return self.build_query_url(self.account_path, user_id, custom)

    def build_salesperson_query_url(self, user_id, custom=None,
                                    offset=None, limit=None):
        return self.build_query_url(self.salespersons_path,
                                    user_id, custom, offset, limit)

    def mocked_get_uos_user(self, user_id):
        account = self.get_account_from_list(user_id, self.sales_customers)
        if account:
            user = self.build_uos_user_info_from_keystone(
                user_id=account.user_id, name=account.name,
                email=account.email)
            return user
        else:
            raise exception.NotFound()

    def test_get_salesperson_of_account_noset(self):
        query_url = self.build_account_query_url(self.demo_account.user_id,
                                                 'salesperson')
        resp = self.get(query_url, headers=self.admin_headers)
        self.assertEqual({}, resp.json_body)

    def test_set_salesperson_of_account(self):
        demo_account = self.demo_account
        sales_account = self.sales_account
        query_url = self.build_account_query_url(demo_account.user_id,
                                                 'salesperson')
        body = {'sales_id': sales_account.user_id}
        self.put(query_url, headers=self.admin_headers, body=body)

        account = self.dbconn.get_account(self.admin_req_context,
                                          demo_account.user_id)
        self.assertEqual(sales_account.user_id, account.sales_id)

    def test_set_nonexist_salesperson_of_account(self):
        demo_account = self.demo_account
        sales_id = self.new_user_id()
        query_url = self.build_account_query_url(demo_account.user_id,
                                                 'salesperson')
        body = {'sales_id': sales_id}
        self.put(query_url, headers=self.admin_headers,
                 body=body, expected_status=404)

        restr = r'WARNING.*Salesperson %s does not have an account' % (
            sales_id)
        self.assertLogging(restr)

    def test_salesadmin_set_salesperson_of_account(self):
        demo_account = self.demo_account
        sales_account = self.sales_account
        query_url = self.build_account_query_url(demo_account.user_id,
                                                 'salesperson')
        body = {'sales_id': sales_account.user_id}
        self.put(query_url, headers=self.sales_admin_account_headers,
                 body=body)
        account = self.dbconn.get_account(self.admin_req_context,
                                          demo_account.user_id)
        self.assertEqual(sales_account.user_id, account.sales_id)

    def test_get_salesperson_of_account(self):
        sales_account = self.sales_account
        customer_account = self.sales_customers[0]
        sales_user_info = self.build_uos_user_info_from_keystone(
            user_id=sales_account.user_id, name='salesperson')
        query_url = self.build_account_query_url(customer_account.user_id,
                                                 'salesperson')
        with mock.patch.object(keystone, 'get_uos_user',
                               return_value=sales_user_info):
            resp = self.get(query_url, headers=self.admin_headers)
            sales_person_info = resp.json_body

        self.assertEqual(sales_account.user_id,
                         sales_person_info['user_id'])
        self.assertEqual(sales_user_info['name'],
                         sales_person_info['user_name'])
        self.assertEqual(sales_user_info['email'],
                         sales_person_info['user_email'])
        self.assertEqual(sales_user_info['real_name'],
                         sales_person_info['real_name'])
        self.assertEqual(sales_user_info['mobile_number'],
                         sales_person_info['mobile_number'])
        self.assertEqual(sales_user_info['company'],
                         sales_person_info['company'])

    def test_normal_user_get_salesperson_of_account_failed(self):
        query_url = self.build_account_query_url(
            self.demo_account.user_id, 'salesperson')
        self.get(query_url, headers=self.demo_headers, expected_status=403)

    def test_salesperson_get_salesperson_of_account_failed(self):
        """Test salesperson get salesperson of account failed.

        Salesperson could not get salesperson information
        from account doesn't belong to him/her.
        """

        customer_account = self.sales_customers[0]
        query_url = self.build_account_query_url(
            customer_account.user_id, 'salesperson')
        self.get(query_url, headers=self.sales_account2_headers,
                 expected_status=403)

    def test_salesperson_get_salesperson_of_account_noset_failed(self):
        """Test salesperson get salesperson of account noset failed.

        Salesperson could not get salesperson information
        from account doesn't belong to any salesperson.
        """

        query_url = self.build_account_query_url(
            self.demo_account.user_id, 'salesperson')
        self.get(query_url, headers=self.sales_account_headers,
                 expected_status=403)

    def test_salesadmin_get_salesperson_of_account(self):
        sales_account = self.sales_account
        customer_account = self.sales_customers[0]
        sales_user_info = self.build_uos_user_info_from_keystone(
            user_id=sales_account.user_id, name='salesperson')
        query_url = self.build_account_query_url(customer_account.user_id,
                                                 'salesperson')
        with mock.patch.object(keystone, 'get_uos_user',
                               return_value=sales_user_info):
            resp = self.get(
                query_url, headers=self.sales_admin_account_headers)
            sales_person_info = resp.json_body

            self.assertEqual(sales_account.user_id,
                             sales_person_info['user_id'])
            self.assertEqual(sales_user_info['name'],
                             sales_person_info['user_name'])
            self.assertEqual(sales_user_info['email'],
                             sales_person_info['user_email'])
            self.assertEqual(sales_user_info['real_name'],
                             sales_person_info['real_name'])
            self.assertEqual(sales_user_info['mobile_number'],
                             sales_person_info['mobile_number'])
            self.assertEqual(sales_user_info['company'],
                             sales_person_info['company'])

    def test_salesadmin_get_salesperson_of_account_noset(self):
        query_url = self.build_account_query_url(self.demo_account.user_id,
                                                 'salesperson')
        user_info = self.build_uos_user_info_from_keystone(
            user_id='test', name='test')
        with mock.patch.object(keystone, 'get_uos_user',
                               return_value=user_info):
            resp = self.get(query_url,
                            headers=self.sales_admin_account_headers)
        self.assertEqual({}, resp.json_body)

    def test_get_accounts_of_salesperson(self):
        def _mocked_get_uos_user(user_id):
            return self.mocked_get_uos_user(user_id)

        sales_account = self.sales_account
        query_url = self.build_salesperson_query_url(sales_account.user_id,
                                                     'accounts')
        with mock.patch.object(keystone, 'get_uos_user',
                               side_effect=_mocked_get_uos_user):
            resp = self.get(query_url, headers=self.admin_headers)
            sales_accounts = resp.json_body

        self.assertEqual(self.customers_number,
                         sales_accounts['total_count'])
        for account_ref in sales_accounts['accounts']:
            account = self.get_account_from_list(account_ref['user_id'],
                                                 self.sales_customers)
            self.assertIsNotNone(account)
            self.assertEqual(account.name, account_ref['user_name'])
            self.assertEqual(account.email, account_ref['user_email'])

    def test_get_accounts_of_salesperson_paginated(self):
        def _mocked_get_uos_user(user_id):
            return self.mocked_get_uos_user(user_id)

        sales_account = self.sales_account

        with mock.patch.object(keystone, 'get_uos_user',
                               side_effect=_mocked_get_uos_user):
            query_url = self.build_salesperson_query_url(
                sales_account.user_id, 'accounts', 0, 3)
            resp = self.get(query_url, headers=self.admin_headers)
            sales_account_refs1 = resp.json_body
            query_url = self.build_salesperson_query_url(
                sales_account.user_id, 'accounts', 3, 3)
            resp = self.get(query_url, headers=self.admin_headers)
            sales_account_refs2 = resp.json_body

            # Fetch same result as sales_account_ref1
            query_url = self.build_salesperson_query_url(
                sales_account.user_id, 'accounts', 0, 3)
            resp = self.get(query_url, headers=self.admin_headers)
            sales_account_refs3 = resp.json_body

        self.assertEqual(self.customers_number,
                         sales_account_refs1['total_count'])
        self.assertEqual(3, len(sales_account_refs1['accounts']))
        self.assertEqual(self.customers_number,
                         sales_account_refs2['total_count'])
        self.assertEqual(3, len(sales_account_refs2['accounts']))

        sales_account_refs = (sales_account_refs1['accounts']
                              + sales_account_refs2['accounts'])
        for account_ref in sales_account_refs:
            account = self.get_account_from_list(account_ref['user_id'],
                                                 self.sales_customers)
            self.assertIsNotNone(account)

        # sales_account_refs3 should equal sales_account_refs1
        for account_ref in sales_account_refs3:
            self.assertIn(account_ref, sales_account_refs1)

    def test_normal_user_get_accounts_of_salesperson_failed(self):
        query_url = self.build_salesperson_query_url(
            self.sales_account.user_id, 'accounts')
        self.get(query_url, headers=self.demo_headers,
                 expected_status=403)

    def test_salesperson_get_accounts_of_another_salesperson_failed(self):
        query_url = self.build_salesperson_query_url(
            self.sales_account2.user_id, 'accounts')
        self.get(query_url, headers=self.sales_account_headers,
                 expected_status=403)

    def test_salesadmin_get_accounts_of_another_salesperson(self):
        def _mocked_get_uos_user(user_id):
            return self.mocked_get_uos_user(user_id)

        sales_account = self.sales_account
        query_url = self.build_salesperson_query_url(
            sales_account.user_id, 'accounts')
        with mock.patch.object(keystone, 'get_uos_user',
                               side_effect=_mocked_get_uos_user):

            resp = self.get(
                query_url, headers=self.sales_admin_account_headers)
            sales_accounts = resp.json_body

        self.assertEqual(self.customers_number,
                         sales_accounts['total_count'])
        for account_ref in sales_accounts['accounts']:
            account = self.get_account_from_list(account_ref['user_id'],
                                                 self.sales_customers)
            self.assertIsNotNone(account)
            self.assertEqual(account.name, account_ref['user_name'])
            self.assertEqual(account.email, account_ref['user_email'])

    def test_get_amount_of_salesperson(self):
        sales_account = self.sales_account
        query_url = self.build_salesperson_query_url(sales_account.user_id,
                                                     'amount')
        resp = self.get(query_url, headers=self.admin_headers)
        amount = resp.json_body
        self.assertEqual(self.customers_number, amount['accounts_number'])

        expected_sales_amount = sum([
            c.consumption for c in self.sales_customers])
        self.assertDecimalEqual(expected_sales_amount, amount['sales_amount'])

    def test_normal_user_get_amount_of_salesperson_failed(self):
        query_url = self.build_salesperson_query_url(
            self.sales_account.user_id, 'amount')
        self.get(query_url, headers=self.demo_headers,
                 expected_status=403)

    def test_salesperson_get_amount_of_another_salesperson_failed(self):
        query_url = self.build_salesperson_query_url(
            self.sales_account2.user_id, 'amount')
        self.get(query_url, headers=self.sales_account_headers,
                 expected_status=403)

    def test_salesadmin_get_amount_of_another_salesperson(self):
        sales_account = self.sales_account
        query_url = self.build_salesperson_query_url(
            sales_account.user_id, 'amount')
        resp = self.get(query_url, headers=self.sales_admin_account_headers)
        amount = resp.json_body
        self.assertEqual(self.customers_number, amount['accounts_number'])

        expected_sales_amount = sum([
            c.consumption for c in self.sales_customers])
        self.assertDecimalEqual(expected_sales_amount, amount['sales_amount'])

    def test_update_salesperson_of_many_accounts(self):
        old_sales_account = self.sales_account
        new_sales_account = self.sales_account2

        user_ids = [a.user_id for a in self.sales_customers]
        body = {'user_ids': user_ids}
        query_url = self.build_salesperson_query_url(
            new_sales_account.user_id, 'accounts')
        self.put(query_url, headers=self.admin_headers, body=body)

        accounts = list(self.dbconn.get_salesperson_customer_accounts(
            self.admin_req_context, new_sales_account.user_id))
        self.assertEqual(self.customers_number, len(accounts))

        accounts = list(self.dbconn.get_salesperson_customer_accounts(
            self.admin_req_context, old_sales_account.user_id))
        self.assertEqual(0, len(accounts))

    def test_salesperson_update_salesperson_of_many_accounts_failed(self):
        new_sales_account = self.sales_account2

        user_ids = [a.user_id for a in self.sales_customers]
        body = {'user_ids': user_ids}
        query_url = self.build_salesperson_query_url(
            new_sales_account.user_id, 'accounts')
        self.put(query_url, headers=self.sales_account_headers,
                 body=body, expected_status=403)

    def test_salesadmin_update_salesperson_of_many_accounts(self):
        new_sales_account = self.sales_account2

        user_ids = [a.user_id for a in self.sales_customers]
        body = {'user_ids': user_ids}
        query_url = self.build_salesperson_query_url(
            new_sales_account.user_id, 'accounts')
        self.put(query_url, headers=self.sales_admin_account_headers,
                 body=body)
