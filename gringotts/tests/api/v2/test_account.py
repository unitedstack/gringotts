
from gringotts.tests import rest


class AccountTestCase(rest.RestfulTestCase):

    def setUp(self):
        super(AccountTestCase, self).setUp()

        self.account_path = '/v2/accounts'
        self.headers = self.build_admin_http_headers()

    def build_account_query_url(self, user_id):
        return self.build_query_url(self.account_path, user_id)

    def test_get_all_accounts(self):
        resp = self.get(self.account_path, headers=self.headers)
        self.assertEqual(2, resp.json_body['total_count'])
        self.assertEqual(2, len(resp.json_body['accounts']))

    def test_get_account_by_user_id(self):
        admin_account = self.admin_account
        account_ref = self.new_account_ref(
            user_id=admin_account.user_id, project_id=admin_account.project_id,
            domain_id=admin_account.domain_id, level=admin_account.level,
            owed=admin_account.owed, balance=admin_account.balance,
            consumption=admin_account.balance)

        query_url = self.build_account_query_url(account_ref['user_id'])
        resp = self.get(query_url, headers=self.headers)
        account = resp.json_body
        self.assertAccountEqual(account_ref, account)

    def test_create_account(self):
        new_user_id = self.new_uuid()
        account_ref = self.new_account_ref(
            new_user_id, self.demo_project_id, self.demo_domain_id,
            level=3, owed=False)
        self.post(self.account_path, headers=self.headers,
                  body=account_ref, expected_status=204)

        account = self.dbconn.get_account(self.admin_req_context, new_user_id)
        self.assertAccountEqual(account.as_dict(), account_ref)

    def test_get_account_estimate(self):
        pass

    def test_get_account_estimate_per_day(self):
        pass

    def test_account_charge(self):
        pass

    def test_account_charge_with_negative_value_failed(self):
        pass
