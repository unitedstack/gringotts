
import datetime

from gringotts.tests import rest


class PrechargeTestCase(rest.RestfulTestCase):

    def setUp(self):
        super(PrechargeTestCase, self).setUp()

        self.precharge_path = '/v2/precharge'
        self.headers = self.build_admin_http_headers()
        self.demo_headers = self.build_demo_http_headers()

    def build_precharge_query_url(self, code, custom=None):
        return self.build_query_url(self.precharge_path, code, custom)

    def test_get_precharge_by_code(self):
        # Create a precharge firstly
        charge_value = 100
        number = 1
        expired_at = self.utcnow() + datetime.timedelta(days=365)
        remarks = 'Create a precharge'
        self.dbconn.create_precharge(
            self.admin_req_context, number=number,
            price=charge_value, expired_at=expired_at,
            remarks=remarks)
        precharges = list(self.dbconn.get_precharges(self.admin_req_context))
        precharge = precharges[0]
        # Get the precharge by code
        query_url = self.build_precharge_query_url(precharge.code)
        resp = self.get(query_url, headers=self.headers)
        precharge_result = resp.json_body
        # Check the get response body
        self.assertPrechargeEqual(precharge.as_dict(), precharge_result)
        self.assertEqual(
            self.date_to_str(precharge.expired_at),
            self.date_to_str(self.datetime_from_isotime_str(
                precharge_result['expired_at']
            ))
        )

    def test_dispatch_and_user_one_precharge(self):
        # Create a precharge firstly
        charge_value = 100
        number = 1
        expired_at = self.utcnow() + datetime.timedelta(days=365)
        remarks = 'Create a precharge'
        self.dbconn.create_precharge(
            self.admin_req_context, number=number,
            price=charge_value, expired_at=expired_at,
            remarks=remarks)
        # Get a precharge
        precharges = list(self.dbconn.get_precharges(self.admin_req_context))
        self.assertEqual(number, len(precharges))
        precharge = precharges[0]
        precharge_code = precharge.code
        query_url = self.build_precharge_query_url(precharge_code,
                                                   'dispatched')
        # Dispatch the precharge
        remarks = 'Why this precharge card being dispatched?'
        body = {'remarks': remarks}
        resp = self.put(query_url, headers=self.headers,
                        body=body, expected_status=200)
        # Check the put response body
        precharge_result = resp.json_body
        self.assertTrue(precharge_result['dispatched'])
        self.assertEqual(remarks, precharge_result['remarks'])
        # Check whether udpate successfully
        body = self.dbconn.get_precharge_by_code(self.admin_req_context,
                                                 code=precharge_code)
        self.assertTrue(body['dispatched'])
        self.assertEqual(remarks, body['remarks'])
        # Demo user use the precharge
        query_url = self.build_precharge_query_url(precharge_code, 'used')
        resp = self.put(query_url, headers=self.demo_headers,
                        expected_status=200)
        body = resp.json_body
        self.assertEqual(body['ret_code'], 0)
        # Check the used status
        body = self.dbconn.get_precharge_by_code(self.admin_req_context,
                                                 code=precharge_code)
        self.assertTrue(body['used'])
        self.assertEqual(self.demo_user_id, body['user_id'])

    def test_delete_one_precharge(self):
        # create a precharge firstly
        charge_value = 100
        number = 1
        expired_at = self.utcnow() + datetime.timedelta(days=365)
        remarks = 'create a precharge'
        self.dbconn.create_precharge(
            self.admin_req_context, number=number,
            price=charge_value, expired_at=expired_at,
            remarks=remarks)
        # get a precharge
        precharges = list(self.dbconn.get_precharges(self.admin_req_context))
        self.assertEqual(number, len(precharges))
        precharge = precharges[0]
        # delete the precharge
        query_url = self.build_precharge_query_url(precharge.code)
        self.delete(query_url, headers=self.headers, expected_status=204)

    def test_use_precharge_not_exist(self):
        pass

    def test_use_precharge_has_used(self):
        pass

    def test_use_precharge_has_expired(self):
        pass

    def test_use_precharge_exceed_count(self):
        pass


class PrechargesTestCase(rest.RestfulTestCase):

    def setUp(self):
        super(PrechargesTestCase, self).setUp()

        self.precharge_path = '/v2/precharge'
        self.headers = self.build_admin_http_headers()
        self.demo_headers = self.build_demo_http_headers()

    def build_precharges_query_url(self, params=None):
        path = self.precharge_path
        if not params:
            return path
        var = []
        for k, v in params.iteritems():
            if k:
                var.append('%s=%s' % (k, v))
        if var:
            path += '?%s' % ('&'.join(var))
        return path

    def test_create_one_precharge(self):
        # Create a precharge
        charge_value = 100
        number = 1
        precharge_ref = self.new_precharge_ref(number, charge_value)
        self.post(self.precharge_path, headers=self.headers,
                  body=precharge_ref, expected_status=201)

        # Check whether create successfully
        precharges = list(self.dbconn.get_precharges(self.admin_req_context))
        self.assertEqual(number, len(precharges))
        precharge = precharges[0]
        self.assertPriceEqual(precharge_ref['price'], precharge.price)

        operator_id = self.admin_user_id
        expired_at = self.utcnow() + datetime.timedelta(days=365)
        self.assertEqual(self.date_to_str(expired_at),
                         self.date_to_str(precharge.expired_at))
        self.assertEqual(operator_id, precharge.operator_id)

    def test_create_many_precharges(self):
        # Create some precharges
        charge_value = 100
        number = 2
        precharge_ref = self.new_precharge_ref(number, charge_value)
        self.post(self.precharge_path, headers=self.headers,
                  body=precharge_ref, expected_status=201)

        # Check whether all create successfully
        precharges = list(self.dbconn.get_precharges(self.admin_req_context))
        self.assertEqual(number, len(precharges))

        operator_id = self.admin_user_id
        expired_at = self.utcnow() + datetime.timedelta(days=365)
        for p in precharges:
            self.assertPriceEqual(precharge_ref['price'], p.price)
            self.assertEqual(self.date_to_str(expired_at),
                             self.date_to_str(p.expired_at))
            self.assertEqual(operator_id, p.operator_id)

    def test_delete_many_precharges(self):
        # Create some precharges
        charge_value = 100
        number = 2
        expired_at = self.utcnow() + datetime.timedelta(days=365)
        remarks = 'Create some precharges'
        self.dbconn.create_precharge(
            self.admin_req_context, number=number,
            price=charge_value, expired_at=expired_at,
            remarks=remarks)
        # Get codes of precharges
        precharges = list(self.dbconn.get_precharges(self.admin_req_context))
        self.assertEqual(number, len(precharges))
        codes = [p['code'] for p in precharges]
        # Delete precharges
        body = {'codes': codes}
        self.delete(self.precharge_path, headers=self.headers,
                    body=body, expected_status=204)
        # Check whether all delete sucessfully
        precharges = list(self.dbconn.get_precharges(self.admin_req_context))
        self.assertEqual(precharges, [])

    def test_dispatch_many_precharges(self):
        # Create some precharges
        charge_value = 100
        number = 2
        expired_at = self.utcnow() + datetime.timedelta(days=365)
        remarks = 'Create some precharges'
        self.dbconn.create_precharge(
            self.admin_req_context, number=number,
            price=charge_value, expired_at=expired_at,
            remarks=remarks)
        # Get codes of precharges
        precharges = list(self.dbconn.get_precharges(self.admin_req_context))
        self.assertEqual(number, len(precharges))
        codes = [p['code'] for p in precharges]

        remarks = 'dispatch a precharge'
        body = {
            'codes': codes,
            'remarks': remarks
        }
        # Dispatch precharges
        query_url = self.precharge_path + '/dispatched'
        self.put(query_url, headers=self.headers,
                 body=body)
        # Check whether all dispatch successfully
        for code in codes:
            p = self.dbconn.get_precharge_by_code(self.admin_req_context, code)
            self.assertTrue(p['dispatched'])
            self.assertEqual(p['remarks'], remarks)

    def test_get_precharges_with_pagination(self):
        # Create some precharges
        charge_value = 100
        number = 30
        expired_at = self.utcnow() + datetime.timedelta(days=365)
        remarks = 'create 30 precharges each values 100 to test pagination'
        self.dbconn.create_precharge(
            self.admin_req_context, number=number,
            price=charge_value, expired_at=expired_at,
            remarks=remarks)
        precharges = list(self.dbconn.get_precharges(self.admin_req_context))
        self.assertEqual(len(precharges), number)
        # Get precharges
        offset = 5
        limit = 25
        kwargs = {
            'limit': limit,
            'offset': offset
        }
        query_url = self.build_precharges_query_url(kwargs)
        resp = self.get(query_url, headers=self.headers)
        results = resp.json_body
        self.assertEqual(results['total_count'], number)
        self.assertEqual(len(results['precharges']), limit)
