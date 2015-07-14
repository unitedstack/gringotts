
import datetime

from gringotts.tests import rest


class PrechargeTestCase(rest.RestfulTestCase):

    def setUp(self):
        super(PrechargeTestCase, self).setUp()

        self.precharge_path = '/v2/precharge'
        self.headers = self.build_admin_http_headers()

    def build_precharge_query_url(self, code, custom=None):
        return self.build_query_url(self.precharge_path, code, custom)

    def test_create_one_precharge(self):
        charge_value = 100
        number = 1
        precharge_ref = self.new_precharge_ref(number, charge_value)
        self.post(self.precharge_path, headers=self.headers,
                  body=precharge_ref, expected_status=204)

        precharges = list(self.dbconn.get_precharges(self.admin_req_context))
        self.assertEqual(number, len(precharges))
        precharge = precharges[0]
        self.assertPriceEqual(precharge_ref['price'], precharge.price)

        expired_at = self.utcnow() + datetime.timedelta(days=365)
        self.assertEqual(self.date_to_str(expired_at),
                         self.date_to_str(precharge.expired_at))

    def test_create_many_precharges(self):
        charge_value = 100
        number = 2
        precharge_ref = self.new_precharge_ref(number, charge_value)
        self.post(self.precharge_path, headers=self.headers,
                  body=precharge_ref, expected_status=204)

        precharges = list(self.dbconn.get_precharges(self.admin_req_context))
        self.assertEqual(number, len(precharges))

        expired_at = self.utcnow() + datetime.timedelta(days=365)
        for p in precharges:
            self.assertPriceEqual(precharge_ref['price'], p.price)
            self.assertEqual(self.date_to_str(expired_at),
                             self.date_to_str(p.expired_at))

    def test_get_precharge_by_code(self):
        charge_value = 100
        number = 1
        expired_at = self.utcnow() + datetime.timedelta(days=365)
        self.dbconn.create_precharge(
            self.admin_req_context, number=number,
            price=charge_value, expired_at=expired_at)
        precharges = list(self.dbconn.get_precharges(self.admin_req_context))
        precharge = precharges[0]
        query_url = self.build_precharge_query_url(precharge.code)
        resp = self.get(query_url, headers=self.headers)
        precharge_result = resp.json_body
        self.assertPrechargeEqual(precharge.as_dict(), precharge_result)
        self.assertEqual(
            self.date_to_str(precharge.expired_at),
            self.date_to_str(self.datetime_from_isotime_str(
                precharge_result['expired_at']
            ))
        )

    def test_dispatch_precharge(self):
        charge_value = 100
        number = 1
        expired_at = self.utcnow() + datetime.timedelta(days=365)
        self.dbconn.create_precharge(
            self.admin_req_context, number=number,
            price=charge_value, expired_at=expired_at)
        precharges = list(self.dbconn.get_precharges(self.admin_req_context))
        precharge = precharges[0]
        precharge_code = precharge.code

        query_url = self.build_precharge_query_url(precharge_code,
                                                   'dispatched')
        remarks = 'Why this precharge card being dispatched?'
        body = {'remarks': remarks}
        resp = self.put(query_url, headers=self.headers,
                        body=body, expected_status=200)
        precharge_result = resp.json_body
        self.assertIs(precharge_result['dispatched'], True)
        self.assertEqual(remarks, precharge_result['remarks'])

    def test_use_precharge(self):
        pass

    def test_use_precharge_not_exist(self):
        pass

    def test_use_precharge_has_used(self):
        pass

    def test_use_precharge_has_expired(self):
        pass

    def test_use_precharge_exceed_count(self):
        pass
