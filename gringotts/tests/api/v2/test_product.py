
import six
import testtools

from gringotts import constants as gring_const
from gringotts import exception
from gringotts.openstack.common import jsonutils
from gringotts.openstack.common import log as logging
from gringotts.price import pricing
from gringotts.tests import rest

LOG = logging.getLogger(__name__)


class ProductTestCase(rest.RestfulTestCase):

    def setUp(self):
        super(ProductTestCase, self).setUp()

        self.product_path = '/v2/products'
        self.product_detail_path = '/v2/products/detail'

        self.admin_headers = self.build_admin_http_headers()
        self.invalid_price_item_restr = \
            r'WARNING.*Segmented price list has invalid price item'

    def build_product_query_url(self, product_id, custom=None):
        return self.build_query_url(self.product_path, product_id, custom)

    def _create_product_with_base_price_failed(self, base_price, restr=None):
        price_list = [[10, '0.1'], [4, '0.2'], [0, '0.3']]
        price_data = self.build_segmented_price_data(
            base_price, price_list)
        product_ref = self.new_product_ref(
            'network', '0.1', 'hour', extra={'price': price_data})
        self.post(self.product_path, headers=self.admin_headers,
                  body=product_ref, expected_status=400)
        if restr:
            self.assertLogging(restr)

    def _create_product_with_price_data_failed(
            self, price_list=None, price_data=None, restr=None):
        if not price_data:
            price_data = self.build_segmented_price_data('0', price_list)
        product_ref = self.new_product_ref(
            'network', '0.1', 'hour', extra={'price': price_data})
        self.post(self.product_path, headers=self.admin_headers,
                  body=product_ref, expected_status=400)
        if restr:
            self.assertLogging(restr)

    def _update_product_with_base_price_failed(self, product, base_price,
                                               restr=None):
        price_list = [[10, '0.1'], [4, '0.2'], [0, '0.3']]
        price_data = self.build_segmented_price_data(
            base_price, price_list)
        extra = {'price': price_data}
        body = {'extra': jsonutils.dumps(extra)}
        query_url = self.build_product_query_url(product.product_id)
        self.put(query_url, headers=self.admin_headers,
                 body=body, expected_status=400)
        if restr:
            self.assertLogging(restr)

    def _update_product_with_price_data_failed(
            self, product, price_list=None, price_data=None, restr=None):
        if not price_data:
            price_data = self.build_segmented_price_data('0', price_list)
        extra = {'price': price_data}
        body = {'extra': jsonutils.dumps(extra)}
        query_url = self.build_product_query_url(product.product_id)
        self.put(query_url, headers=self.admin_headers,
                 body=body, expected_status=400)
        if restr:
            self.assertLogging(restr)

    def test_get_all_products(self):
        resp = self.get(self.product_path, headers=self.admin_headers)
        self.assertEqual(self.product_fixture.total, len(resp.json_body))

    def test_get_all_products_in_detail(self):
        resp = self.get(self.product_detail_path, headers=self.admin_headers)
        self.assertEqual(self.product_fixture.total,
                         resp.json_body['total_count'])
        self.assertEqual(self.product_fixture.total,
                         len(resp.json_body['products']))
        self.assertIn('product_id', resp.json_body['products'][0])

    def test_get_product_by_id(self):
        product = self.product_fixture.instance_products[0]
        query_url = self.build_product_query_url(product.product_id)
        resp = self.get(query_url, headers=self.admin_headers)
        product_ref = resp.json_body
        self.assertEqual(product.product_id, product_ref['product_id'])

    def test_create_product(self):
        product_ref = self.new_product_ref('network', '0.01', 'hour')
        resp = self.post(self.product_path, headers=self.admin_headers,
                         body=product_ref, expected_status=200)
        product_new_ref = resp.json_body
        self.assertProductEqual(product_ref, product_new_ref)

    def test_create_duplicate_product_failed(self):
        product = self.product_fixture.instance_products[0]
        product_ref = self.new_product_ref(
            product.service, float(product.unit_price), product.unit)
        product_ref['name'] = product.name
        product_ref['region_id'] = product.region_id
        # TODO(liuchenhong): failed response code should be 400
        self.post(self.product_path, headers=self.admin_headers,
                  body=product_ref, expected_status=500)

    def test_update_product_unit_price(self):
        product = self.product_fixture.instance_products[0]
        product_id = product.product_id
        new_unit_price = product.unit_price + self.quantize(0.1)
        product_ref = self.new_product_ref(
            product.service, float(new_unit_price), product.unit)
        product_ref['name'] = product.name
        product_ref['region_id'] = product.region_id

        query_url = self.build_product_query_url(product_id)
        resp = self.put(query_url, headers=self.admin_headers,
                        body=product_ref, expected_status=200)
        product_new_ref = resp.json_body
        self.assertProductEqual(product_ref, product_new_ref)

    def test_update_product_name(self):
        product = self.product_fixture.instance_products[0]
        product_id = product.product_id
        new_name = product.name + 'new'
        product_ref = self.new_product_ref(
            product.service, float(product.unit_price), product.unit)
        product_ref['name'] = new_name
        product_ref['region_id'] = product.region_id

        query_url = self.build_product_query_url(product_id)
        resp = self.put(query_url, headers=self.admin_headers,
                        body=product_ref, expected_status=200)
        product_new_ref = resp.json_body
        self.assertProductEqual(product_ref, product_new_ref)

    def test_update_product_to_be_duplicated_failed(self):
        product_one = self.product_fixture.instance_products[0]
        product_two = self.product_fixture.instance_products[1]

        product_ref = self.new_product_ref(
            product_one.service, float(product_one.unit_price),
            product_one.unit)
        # make a conflicted update
        product_ref['name'] = product_two.name
        product_ref['service'] = product_two.service
        product_ref['region_id'] = product_two.region_id

        query_url = self.build_product_query_url(product_one.product_id)
        self.put(query_url, headers=self.admin_headers, body=product_ref,
                 expected_status=500)

    def test_delete_product(self):
        product = self.product_fixture.instance_products[0]
        product_id = product.product_id
        query_url = self.build_product_query_url(product_id)
        self.delete(query_url, headers=self.admin_headers)

        with testtools.ExpectedException(exception.ProductIdNotFound):
            self.dbconn.get_product(self.build_admin_req_context(),
                                    product_id)

    def test_create_product_with_invalid_extra_data_failed(self):
        extra = u'{"price": "a"[],}'
        product_ref = self.new_product_ref(
            'network', '0.1', 'hour', extra)
        self.post(self.product_path, headers=self.admin_headers,
                  body=product_ref, expected_status=400)

    def test_create_product_with_unsupported_pricing_type_failed(self):
        price_data = self.build_segmented_price_data(
            '5.0000', [[10, '0.1'], [4, '0.2'], [0, '0.3']])
        price_data['type'] = 'unsupported'
        extra = {'price': price_data}
        product_ref = self.new_product_ref(
            'network', '0.1', 'hour', extra=extra)
        self.post(self.product_path, headers=self.admin_headers,
                  body=product_ref, expected_status=400)
        restr = r'WARNING.*Unsupported pricing type'
        self.assertLogging(restr)

    def test_create_product_with_segmented_price(self):
        price_data = self.build_segmented_price_data(
            '5.0000', [[10, '0.1'], [4, '0.2'], [0, '0.3']])
        extra = {'price': price_data}
        product_ref = self.new_product_ref(
            'network', '0.1', 'hour', extra=extra)
        resp = self.post(self.product_path, headers=self.admin_headers,
                         body=product_ref, expected_status=200)
        product_new_ref = resp.json_body
        self.assertProductEqual(product_ref, product_new_ref)
        self.assertEqual(extra, jsonutils.loads(product_new_ref['extra']))

    def test_update_product_to_segmented_price(self):
        product = self.product_fixture.ip_products[0]
        price_data = self.build_segmented_price_data(
            '5.0000', [[10, '0.1'], [4, '0.2'], [0, '0.3']])
        extra = {'price': price_data}
        data = {
            'extra': jsonutils.dumps(extra)
        }
        query_url = self.build_product_query_url(product.product_id)
        resp = self.put(query_url, headers=self.admin_headers,
                        body=data, expected_status=200)
        product_ref = resp.json_body
        self.assertProductEqual(product.as_dict(), product_ref)
        self.assertEqual(extra,
                         jsonutils.loads(product_ref['extra']))

    def test_create_product_with_negative_base_price_failed(self):
        restr = r'WARNING.*Base price should not be negative'
        self._create_product_with_base_price_failed('-0.1', restr)

    def test_create_product_with_non_str_base_price_failed(self):
        restr = r'WARNING.*Invalid base price type, should be string'
        self._create_product_with_base_price_failed(1, restr)

    def test_create_product_segmented_price_non_int_quantity_failed(self):
        self._create_product_with_price_data_failed(
            price_list=[['0', '0.1']], restr=self.invalid_price_item_restr)

    def test_create_product_segmented_price_float_price_failed(self):
        self._create_product_with_price_data_failed(
            price_list=[[0, 0.1]], restr=self.invalid_price_item_restr)

    def test_create_product_segmented_price_int_price_failed(self):
        self._create_product_with_price_data_failed(
            price_list=[[0, 1]], restr=self.invalid_price_item_restr)

    def test_create_product_segmented_price_negative_price_failed(self):
        self._create_product_with_price_data_failed(
            price_list=[[0, '-0.1']], restr=self.invalid_price_item_restr)

    def test_create_product_segmented_price_zero_price_failed(self):
        self._create_product_with_price_data_failed(
            price_list=[[0, '0']], restr=self.invalid_price_item_restr)

    def test_create_product_segmented_price_duplicate_items_failed(self):
        price_list = [[0, '0.1'], [0, '0.2']]
        restr = r'WARNING.*Segmented price list has duplicate items'
        self._create_product_with_price_data_failed(
            price_list=price_list, restr=restr)

    def test_create_product_segmented_price_non_from_zero_failed(self):
        price_list = [[1, '0.1'], [10, '0.2']]
        restr = r'WARNING.*Number of resource should start from 0'
        self._create_product_with_price_data_failed(
            price_list=price_list, restr=restr)

    def test_create_product_segmented_price_without_segmented_failed(self):
        price_data = self.build_segmented_price_data('0', None)
        del price_data['segmented']
        restr = 'WARNING.*No segmented price list in price data'
        self._create_product_with_price_data_failed(
            price_data=price_data, restr=restr)

    def test_create_product_segmented_price_with_nonlist_failed(self):
        price_data = self.build_segmented_price_data('0', None)
        restr = 'WARNING.*No segmented price list in price data'
        self._create_product_with_price_data_failed(
            price_data=price_data, restr=restr)

    def test_create_product_with_unsorted_segmented_price(self):
        price_data = self.build_segmented_price_data(
            '5.0000', [[0, '0.4'], [2, '0.3'], [4, '0.2'], [10, '0.1']])
        product_ref = self.new_product_ref(
            'network', '0.1', 'hour', extra={'price': price_data})
        resp = self.post(self.product_path, headers=self.admin_headers,
                         body=product_ref, expected_status=200)
        product_new_ref = resp.json_body
        self.assertProductEqual(product_ref, product_new_ref)
        # price list must be sorted after successfully created
        price_data['segmented'] = [
            [10, '0.1'], [4, '0.2'], [2, '0.3'], [0, '0.4']
        ]
        self.assertEqual({'price': price_data},
                         jsonutils.loads(product_new_ref['extra']))

    def test_update_product_with_negative_base_price_failed(self):
        product = self.product_fixture.ip_products[0]
        restr = r'WARNING.*Base price should not be negative'
        self._update_product_with_base_price_failed(product, '-0.1', restr)

    def test_update_product_with_non_str_base_price_failed(self):
        product = self.product_fixture.ip_products[0]
        restr = r'WARNING.*Invalid base price type, should be string'
        self._update_product_with_base_price_failed(product, 0, restr)

    def test_update_product_segmented_price_non_int_quantity_failed(self):
        product = self.product_fixture.ip_products[0]
        self._update_product_with_price_data_failed(
            product, price_list=[['0', '0.1']],
            restr=self.invalid_price_item_restr)

    def test_update_product_segmented_price_float_price_failed(self):
        product = self.product_fixture.ip_products[0]
        self._update_product_with_price_data_failed(
            product, price_list=[[0, 0.1]],
            restr=self.invalid_price_item_restr)

    def test_update_product_segmented_price_int_price_failed(self):
        product = self.product_fixture.ip_products[0]
        self._update_product_with_price_data_failed(
            product, price_list=[[0, 1]],
            restr=self.invalid_price_item_restr)

    def test_update_product_segmented_price_negative_price_failed(self):
        product = self.product_fixture.ip_products[0]
        self._update_product_with_price_data_failed(
            product, price_list=[[0, '-0.1']],
            restr=self.invalid_price_item_restr)

    def test_update_product_segmented_price_zero_price_failed(self):
        product = self.product_fixture.ip_products[0]
        self._update_product_with_price_data_failed(
            product, price_list=[[0, '0']],
            restr=self.invalid_price_item_restr)

    def test_update_product_segmented_price_duplicate_items_failed(self):
        product = self.product_fixture.ip_products[0]
        price_list = [[0, '0.1'], [0, '0.2']]
        restr = r'WARNING.*Segmented price list has duplicate items'
        self._update_product_with_price_data_failed(
            product, price_list=price_list, restr=restr)

    def test_update_product_segmented_price_non_from_zero_failed(self):
        product = self.product_fixture.ip_products[0]
        price_list = [[1, '0.1'], [10, '0.2']]
        restr = r'WARNING.*Number of resource should start from 0'
        self._update_product_with_price_data_failed(
            product, price_list=price_list, restr=restr)

    def test_update_product_segmented_price_without_segmented_failed(self):
        product = self.product_fixture.ip_products[0]
        price_data = self.build_segmented_price_data('0', None)
        del price_data['segmented']
        restr = 'WARNING.*No segmented price list in price data'
        self._update_product_with_price_data_failed(
            product, price_data=price_data, restr=restr)

    def test_update_product_segmented_price_with_nonlist_failed(self):
        product = self.product_fixture.ip_products[0]
        price_data = self.build_segmented_price_data('0', None)
        restr = 'WARNING.*No segmented price list in price data'
        self._update_product_with_price_data_failed(
            product, price_data=price_data, restr=restr)

    def test_update_product_with_unsorted_segmented_price(self):
        product = self.product_fixture.ip_products[0]
        price_data = self.build_segmented_price_data(
            '5.0000', [[0, '0.4'], [2, '0.3'], [4, '0.2'], [10, '0.1']])
        extra = {'price': price_data}
        body = {'extra': jsonutils.dumps(extra)}
        query_url = self.build_product_query_url(product.product_id)
        resp = self.put(query_url, headers=self.admin_headers,
                        body=body, expected_status=200)
        product_ref = resp.json_body
        self.assertProductEqual(product.as_dict(), product_ref)
        # price list must be sorted after successfully created
        price_data['segmented'] = [
            [10, '0.1'], [4, '0.2'], [2, '0.3'], [0, '0.4']
        ]
        self.assertEqual({'price': price_data},
                         jsonutils.loads(product_ref['extra']))

    def test_update_product_with_segmented_price_and_reset(self):
        product = self.product_fixture.ip_products[0]
        quantity = 11
        resource_type = gring_const.RESOURCE_FLOATINGIP
        order_id = self.new_order_id()
        user_id = self.admin_account.user_id
        project_id = self.admin_account.project_id

        running_subs = self.create_subs_in_db(
            product, quantity, gring_const.STATE_RUNNING,
            order_id, project_id, user_id
        )
        order = self.create_order_in_db(
            running_subs.unit_price, running_subs.unit,
            user_id, project_id, resource_type,
            running_subs.type, order_id=order_id
        )

        price_data = self.build_segmented_price_data(
            '0.0000', [[10, '0.1'], [4, '0.2'], [0, '0.3']])
        extra = {'price': price_data}
        body = {
            'extra': jsonutils.dumps(extra),
            'reset': True,
        }
        query_url = self.build_product_query_url(product.product_id)
        self.put(query_url, headers=self.admin_headers,
                 body=body, expected_status=200)

        expected_price = pricing.calculate_price(
            quantity, product.unit_price, price_data)
        order = self.dbconn.get_order(self.admin_req_context, order.order_id)
        subs = list(self.dbconn.get_subscriptions_by_order_id(
            self.admin_req_context, order.order_id))
        for sub in subs:
            self.assertEqual(extra, jsonutils.loads(sub.extra))
        self.assertDecimalEqual(expected_price, order.unit_price)

    def test_get_product_detail_with_negative_limit_or_offset(self):
        path = "%s/%s" % (self.product_path, 'detail')
        self.check_invalid_limit_or_offset(path)

    def test_get_all_products_with_negative_limit_or_offset(self):
        path = self.product_path
        self.check_invalid_limit_or_offset(path)


class ProductPriceTestCase(rest.RestfulTestCase):

    def setUp(self):
        super(ProductPriceTestCase, self).setUp()

        self.price_path = '/v2/products/price'
        self.admin_headers = self.build_admin_http_headers()
        self.price_data = self.build_segmented_price_data(
            '0.0000', [[10, '0.1'], [4, '0.2'], [0, '0.3']])

    def set_product_to_segmented_price(self, product):
        extra = {'price': self.price_data}
        return self.update_product_in_db(product.product_id, extra=extra)

    def build_price_query_url(self, purchases, bill_method='hour'):
        query_vars = ['purchase.bill_method=%s' % bill_method]
        for i, p in enumerate(purchases):
            for k, v in six.iteritems(p):
                query_vars.append('purchase.purchases[%d].%s=%s' % (i, k, v))

        query_parts = '&'.join(query_vars)
        LOG.debug(query_parts)
        return self.price_path + '?' + query_parts

    def build_purchase(self, product_name, service, region_id, quantity):
        p = {
            'product_name': product_name,
            'service': service,
            'region_id': region_id,
            'quantity': quantity,
        }
        return p

    def query_price(self, product, quantity):
        purchase = self.build_purchase(
            product.name, product.service, product.region_id, quantity)
        query_url = self.build_price_query_url([purchase])
        resp = self.get(query_url, headers=self.admin_headers)
        return resp.json_body

    def test_get_price_of_floatingip_with_unit_price(self):
        product = self.product_fixture.ip_products[0]

        price_ref = self.query_price(product, 1)
        hourly_price = pricing.calculate_price(1, product.unit_price)
        self.assertDecimalEqual(hourly_price, price_ref['unit_price'])

        price_ref = self.query_price(product, 10)
        hourly_price = pricing.calculate_price(10, product.unit_price)
        self.assertDecimalEqual(hourly_price, price_ref['unit_price'])

    def test_get_price_of_floatingip_with_segmented_price(self):
        product = self.product_fixture.ip_products[0]
        product = self.set_product_to_segmented_price(product)

        price_ref = self.query_price(product, 1)
        hourly_price = pricing.calculate_price(
            1, product.unit_price, self.price_data)
        self.assertDecimalEqual(hourly_price, price_ref['unit_price'])

        price_ref = self.query_price(product, 10)
        hourly_price = pricing.calculate_price(
            10, product.unit_price, self.price_data)
        self.assertDecimalEqual(hourly_price, price_ref['unit_price'])

    def test_get_price_of_nonexist_product_failed(self):
        product = self.product_fixture.ip_products[0]
        purchase = self.build_purchase(
            self.new_uuid(), product.service, product.region_id, 1)
        query_url = self.build_price_query_url([purchase])
        self.get(query_url, headers=self.admin_headers,
                 expected_status=404)

    def test_get_price_of_product_with_nonzero_index(self):
        product = self.product_fixture.ip_products[0]
        quantity = 1
        purchase = self.build_purchase(
            product.name, product.service, product.region_id, quantity)
        price = pricing.calculate_price(quantity, product.unit_price)
        query_vars = ['purchase.bill_method=hour']
        for k, v in six.iteritems(purchase):
            query_vars.append('purchase.purchases[1].%s=%s' % (k, v))

        query_parts = '&'.join(query_vars)
        LOG.debug(query_parts)
        query_url = self.price_path + '?' + query_parts
        resp = self.get(query_url, headers=self.admin_headers)
        price_ref = resp.json_body
        LOG.debug(price_ref)
        self.assertDecimalEqual(price, price_ref['unit_price'])

    def test_get_price_of_two_products(self):
        quantity = 1
        product1 = self.product_fixture.instance_products[0]
        product2 = self.product_fixture.instance_products[1]
        price1 = pricing.calculate_price(quantity, product1.unit_price)
        price2 = pricing.calculate_price(quantity, product2.unit_price)
        purchase1 = self.build_purchase(
            product1.name, product1.service, product1.region_id, quantity)
        purchase2 = self.build_purchase(
            product2.name, product2.service, product2.region_id, quantity)
        query_url = self.build_price_query_url([purchase1, purchase2])
        resp = self.get(query_url, headers=self.admin_headers)
        price_ref = resp.json_body
        self.assertDecimalEqual(price1 + price2, price_ref['unit_price'])
