
import testtools

from gringotts import exception
from gringotts.openstack.common import log as logging
from gringotts.tests import rest

LOG = logging.getLogger(__name__)


class ProductTestCase(rest.RestfulTestCase):

    def setUp(self):
        super(ProductTestCase, self).setUp()

        self.product_path = '/v2/products'
        self.product_detail_path = '/v2/products/detail'

        self.headers = self.build_admin_http_headers()

    def build_product_query_url(self, product_id):
        return self.build_query_url(self.product_path, product_id)

    def test_get_all_products(self):
        resp = self.get(self.product_path, headers=self.headers)
        self.assertEqual(self.product_fixture.total, len(resp.json_body))

    def test_get_all_products_in_detail(self):
        resp = self.get(self.product_detail_path, headers=self.headers)
        self.assertEqual(self.product_fixture.total,
                         resp.json_body['total_count'])
        self.assertEqual(self.product_fixture.total,
                         len(resp.json_body['products']))
        self.assertIn('product_id', resp.json_body['products'][0])

    def test_get_product_by_id(self):
        product_ref = self.product_fixture.instance_products[0]
        query_url = self.build_product_query_url(product_ref.product_id)
        resp = self.get(query_url, headers=self.headers)
        product = resp.json_body
        self.assertEqual(product_ref.product_id, product['product_id'])

    def test_create_new_product(self):
        product_ref = self.new_product_ref('network', float('0.01'), 'hour')
        resp = self.post(self.product_path, headers=self.headers,
                         body=product_ref, expected_status=200)
        product = resp.json_body
        self.assertProductEqual(product_ref, product)

    def test_create_duplicate_product_failed(self):
        product_one = self.product_fixture.instance_products[0]
        product_ref = self.new_product_ref(
            product_one.service, float(product_one.unit_price),
            product_one.unit)
        product_ref['name'] = product_one.name
        product_ref['region_id'] = product_one.region_id
        # TODO(liuchenhong): failed response code should be 400
        self.post(self.product_path, headers=self.headers,
                  body=product_ref, expected_status=500)

    def test_update_product_unit_price(self):
        product_one = self.product_fixture.instance_products[0]
        product_id = product_one.product_id
        new_unit_price = product_one.unit_price + self.quantize(0.1)
        product_ref = self.new_product_ref(
            product_one.service, float(new_unit_price), product_one.unit)
        product_ref['name'] = product_one.name
        product_ref['region_id'] = product_one.region_id

        query_url = self.build_product_query_url(product_id)
        resp = self.put(query_url, headers=self.headers,
                        body=product_ref, expected_status=200)
        product = resp.json_body
        self.assertProductEqual(product_ref, product)

    def test_update_product_name(self):
        product_one = self.product_fixture.instance_products[0]
        product_id = product_one.product_id
        new_name = product_one.name + 'new'
        product_ref = self.new_product_ref(
            product_one.service, float(product_one.unit_price),
            product_one.unit)
        product_ref['name'] = new_name
        product_ref['region_id'] = product_one.region_id

        query_url = self.build_product_query_url(product_id)
        resp = self.put(query_url, headers=self.headers,
                        body=product_ref, expected_status=200)
        product = resp.json_body
        self.assertProductEqual(product_ref, product)

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
        self.put(query_url, headers=self.headers, body=product_ref,
                 expected_status=500)

    def test_delete_product(self):
        product_one = self.product_fixture.instance_products[0]
        product_id = product_one.product_id
        query_url = self.build_product_query_url(product_id)
        self.delete(query_url, headers=self.headers)

        with testtools.ExpectedException(exception.ProductIdNotFound):
            self.dbconn.get_product(self.build_admin_req_context(),
                                    product_id)
