
from oslo_config import cfg
import six

from gringotts.openstack.common import jsonutils
from gringotts.openstack.common import log as logging
from gringotts.tests import core as tests
from gringotts.tests import utils as test_utils


CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class RestfulTestCase(tests.TestCase,
                      test_utils.ServiceTestMixin,
                      test_utils.PricingTestMixin):

    def setUp(self):
        super(RestfulTestCase, self).setUp()

    def load_sample_data(self):
        super(RestfulTestCase, self).load_sample_data()

    def build_query_url(self, path_prefix, id, custom=None,
                        offset=None, limit=None):
        path = '%s/%s' % (path_prefix, id)
        if custom:
            path += '/%s' % custom

        var = []
        if offset:
            var.append('offset=%s' % offset)
        if limit:
            var.append('limit=%s' % limit)
        if var:
            path += '?%s' % ('&'.join(var))

        return path

    def assertResponseStatus(self, response, expected_status):
        """Assert a specific status code on the response"""
        self.assertEqual(
            expected_status, response.status_code,
            'Status code %s is not %s, as expected\n\n%s' %
            (response.status_code, expected_status, response.body))

    def request(self, path, method='GET', body=None, headers=None,
                expected_status=None, **kwargs):

        headers = {} if not headers else headers
        headers['Accept'] = 'application/json'
        json_body = body
        if body:
            if not isinstance(body, str):
                json_body = jsonutils.dumps(body)
            headers['Content-Type'] = 'application/json'

        resp = self.app.request(path, headers=headers, body=json_body,
                                status=expected_status,
                                method=method, **kwargs)
        return resp

    def get(self, path, **kwargs):
        r = self.request(path=path, method='GET', **kwargs)
        if 'expected_status' not in kwargs:
            self.assertResponseStatus(r, 200)
        return r

    def head(self, path, **kwargs):
        r = self.request(path=path, method='HEAD', **kwargs)
        if 'expected_status' not in kwargs:
            self.assertREsponseStatus(r, 204)
        self.assertEqual('', r.body)
        return r

    def post(self, path, **kwargs):
        r = self.request(path=path, method='POST', **kwargs)
        if 'expected_status' not in kwargs:
            self.assertResponseStatus(r, 201)
        return r

    def put(self, path, **kwargs):
        r = self.request(path=path, method='PUT', **kwargs)
        if 'expected_status' not in kwargs:
            self.assertResponseStatus(r, 204)
        return r

    def patch(self, path, **kwargs):
        r = self.request(path=path, method='PATCH', **kwargs)
        if 'expected_status' not in kwargs:
            self.assertResponseStatus(r, 200)
        return r

    def delete(self, path, **kwargs):
        r = self.request(path=path, method='DELETE', **kwargs)
        if 'expected_status' not in kwargs:
            self.assertResponseStatus(r, 204)
        return r

    def assertPriceEqual(self, price1, price2, message=''):
        self.assertEqual(self.quantize(price1), self.quantize(price2),
                         message)

    def assertDictEqual(self, dict1, dict2, key_list):
        for key in key_list:
            if key in dict1 and key in dict2:
                self.assertEqual(dict1[key], dict2[key],
                                 'key [%s] mismatch' % key)

    def assertDictDecimalEqual(self, dict1, dict2, key_list):
        for key in key_list:
            self.assertPriceEqual(dict1[key], dict2[key],
                                  'key [%s] mismatch' % key)

    def assertAccountEqual(self, account1, account2):
        key_list = [
            'user_id', 'project_id', 'domain_id', 'level',
            'owed', 'inviter', 'sales_id',
        ]
        self.assertDictEqual(account1, account2, key_list)

        key_list = ['balance', 'consumption']
        self.assertDictDecimalEqual(account1, account2, key_list)

    def assertProductEqual(self, product1, product2):
        key_list = ['name', 'service', 'unit', 'region_id']
        self.assertDictEqual(product1, product2, key_list)

        key_list = ['unit_price']
        self.assertDictDecimalEqual(product1, product2, key_list)

    def assertProjectEqual(self, project1, project2):
        key_list = ['user_id', 'project_id', 'domain_id']
        self.assertDictEqual(project1, project2, key_list)

        key_list = ['consumption']
        self.assertDictDecimalEqual(project1, project2, key_list)

    def assertInUserProjectsList(self, user_id, project_id, user_projects):
        match = False
        for p in user_projects:
            if (user_id == p['user_id'] and project_id == p['project_id']):
                match = True
                break

        self.assertIs(match, True, 'User projects mismatched')

    def assertSubsEqual(self, subs1, subs2):
        key_list = ['order_id', 'product_id', 'project_id', 'user_id']
        for key in key_list:
            self.assertDictEqual(subs1, subs2, key_list)

    def assertInSubsList(self, subs, subs_list):
        for each_subs in subs_list:
            self.assertSubsEqual(subs, each_subs.as_dict())

    def assertOrderEqual(self, order1, order2):
        key_list = [
            'order_id', 'user_id', 'project_id', 'type', 'status',
            'resource_id', 'resource_name',
        ]
        self.assertDictEqual(order1, order2, key_list)

        key_list = ['unit_price']
        self.assertDictDecimalEqual(order1, order2, key_list)

    def assertBillResultEqual(self, bill_result1, bill_result2):
        key_list = [
            'user_id', 'project_id', 'region_id', 'resource_id',
        ]
        self.assertDictEqual(bill_result1, bill_result2, key_list)

    def assertBillMatchOrder(self, bill, order):
        key_list = [
            'region_id', 'domain_id', 'project_id', 'user_id',
            'resource_id', 'order_id', 'unit', 'type',
        ]
        self.assertDictEqual(bill, order, key_list)
        key_list = ['unit_price']
        self.assertDictDecimalEqual(bill, order, key_list)

    def assertPrechargeEqual(self, precharge1, precharge2):
        key_list = [
            'code', 'used', 'dispatched', 'user_id', 'project_id',
        ]
        self.assertDictEqual(precharge1, precharge2, key_list)
        key_list = ['price']
        self.assertDictDecimalEqual(precharge1, precharge2, key_list)

    def new_ref(self):
        ref = {
            'id': self.new_uuid(),
            'name': self.new_uuid(),
            'description': self.new_uuid(),
            'region_id': CONF.region_name,
        }
        return ref

    def new_simple_ref(self):
        ref = {
            'id': self.new_uuid(),
            'region_id': CONF.region_name,
        }
        return ref

    def new_account_ref(self, user_id, project_id, domain_id, level=3,
                        owed=False, balance=0, frozen_balance=0, consumption=0,
                        inviter=None, sales_id=None):
        ref = {}
        ref['user_id'] = user_id
        ref['project_id'] = project_id
        ref['domain_id'] = domain_id
        ref['level'] = level
        ref['owed'] = owed
        ref['balance'] = balance
        ref['frozen_balance'] = frozen_balance
        ref['consumption'] = consumption
        if inviter:
            ref['inviter'] = inviter
        if sales_id:
            ref['sales_id'] = sales_id

        return ref

    def new_product_ref(self, service, unit_price, unit, extra=None):
        ref = self.new_ref()
        del ref['id']
        ref['service'] = service
        ref['unit_price'] = str(unit_price)
        ref['unit'] = unit
        ref['type'] = 'regular'
        if extra:
            ref['extra'] = extra if isinstance(extra, six.text_type) else \
                jsonutils.dumps(extra)
        else:
            ref['extra'] = None

        return ref

    def new_project_ref(self, user_id=None, project_id=None,
                        domain_id=None, consumption=0):
        ref = {}
        ref['user_id'] = user_id if user_id else self.new_uuid()
        ref['project_id'] = project_id if project_id else self.new_uuid()
        ref['domain_id'] = domain_id if domain_id else self.new_uuid()
        ref['consumption'] = consumption

        return ref

    def new_subs_ref(self, service, product_name, resource_volume,
                     type, order_id, project_id, user_id,
                     region_id=CONF.region_name):
        subs_ref = self.new_simple_ref()
        del subs_ref['id']
        subs_ref['service'] = service
        subs_ref['product_name'] = product_name
        subs_ref['resource_volume'] = resource_volume
        subs_ref['type'] = type
        subs_ref['order_id'] = order_id
        subs_ref['project_id'] = project_id
        subs_ref['user_id'] = user_id
        subs_ref['region_id'] = region_id

        return subs_ref

    def new_order_ref(self, unit_price, unit, user_id, project_id,
                      resource_type, status, order_id=None, resource_id=None,
                      resource_name=None):
        order_ref = self.new_simple_ref()
        del order_ref['id']
        order_ref['order_id'] = order_id if order_id else self.new_order_id()
        order_ref['unit_price'] = str(unit_price)
        order_ref['unit'] = unit
        order_ref['user_id'] = user_id
        order_ref['project_id'] = project_id
        order_ref['type'] = resource_type
        order_ref['status'] = status
        order_ref['resource_id'] = \
            resource_id if resource_id else self.new_resource_id()
        order_ref['resource_name'] = \
            resource_name if resource_name else order_ref['resource_id']

        return order_ref

    def new_order_put_ref(self, order_id, new_status, cron_time=None,
                          change_order_status=True, first_change_to=None):
        order_put_ref = {
            'order_id': order_id,
            'change_to': new_status,
            'cron_time': cron_time,
            'change_order_status': change_order_status,
            'first_change_to': first_change_to,
        }
        return order_put_ref

    def new_bill_ref(self, order_id, action_time=None, remarks=None,
                     end_time=None):
        bill_ref = {
            'order_id': order_id,
            'action_time': action_time,
            'remarks': remarks,
            'end_time': end_time,
        }
        return bill_ref

    def new_precharge_ref(self, number, price, expired_at=None, remarks=None):
        precharge_ref = {
            'number': number,
            'price': str(price),
        }
        if expired_at:
            # let it be wsme.Unset if expired_at is None
            precharge_ref['expired_at'] = expired_at
        if remarks:
            # let it be wsme.Unset if remarks is None
            precharge_ref['remarks'] = remarks
        return precharge_ref

    def check_invalid_limit_or_offset(self, path):
        def _check_invalid_limit_or_offset(offset, limit, path):
            query_url = "%s?limit=%s&offset=%s" % (path, limit, offset)
            self.get(query_url, headers=self.build_admin_http_headers(),
                     expected_status=400)
            if limit < 0:
                self.assertLogging(r'WARNING.*Invalid limit')
            if offset < 0:
                self.assertLogging(r'WARNING.*Invalid offset')

        _check_invalid_limit_or_offset(-1, 0, path)
        _check_invalid_limit_or_offset(0, -1, path)
        _check_invalid_limit_or_offset(-1, -1, path)
