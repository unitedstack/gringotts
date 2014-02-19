import decimal
from gringotts.tests import db_fixtures
from gringotts.tests.api.v1 import FunctionalTest


class TestProducts(FunctionalTest):
    PATH = '/products'

    def setUp(self):
        super(TestProducts, self).setUp()
        self.headers = {'X-Roles': 'admin'}
        self.product_1 = {
            "region_id": "default",
            "service": "network",
            "description": "some decs",
            "unit_price": "0.0500",
            "name": "product-1",
            "type": "regular",
            "unit": "hour"
        }

    def test_post_product(self):
        self.post_json(self.PATH, self.product_1, headers=self.headers)
        data = self.get_json(self.PATH, headers=self.headers)
        self.assertEqual(1, len(data))
        self.assertEqual('product-1', data[0]['name'])

    def test_post_product_duplicated(self):
        self.post_json(self.PATH, self.product_1, headers=self.headers)
        resp = self.post_json(self.PATH, self.product_1, expect_errors=True,
                              headers=self.headers)
        self.assertEqual(500, resp.status_int)

    def test_put_product(self):
        self.post_json(self.PATH, self.product_1, headers=self.headers)
        products = self.get_json(self.PATH, headers=self.headers)

        products[0].update(unit_price='0.0600')

        put_path = self.PATH + '/' + products[0]['product_id']
        self.put_json(put_path, products[0], headers=self.headers)

        data = self.get_json(self.PATH, headers=self.headers)
        self.assertEqual('0.0600', data[0]['unit_price'])

    def test_put_product_to_duplicated(self):

        self.product_2 = {
            "region_id": "default",
            "service": "network",
            "description": "some decs",
            "unit_price": "0.0500",
            "name": "product-2",
            "type": "regular",
            "unit": "hour"
        }

        self.post_json(self.PATH, self.product_1, headers=self.headers)
        self.post_json(self.PATH, self.product_2, headers=self.headers)

        products = self.get_json(self.PATH, headers=self.headers)

        # Change product-1's name to product-2
        products[1].update(name='product-2') 

        put_path = self.PATH + '/' + products[1]['product_id']
        resp = self.put_json(put_path, products[1], expect_errors=True,
                             headers=self.headers)

        self.assertEqual(500, resp.status_int)

    def test_delete_product(self):
        self.post_json(self.PATH, self.product_1, headers=self.headers)
        products = self.get_json(self.PATH, headers=self.headers)

        path = self.PATH + '/' + products[0]['product_id']
        self.delete(path, headers=self.headers)
        products = self.get_json(self.PATH, headers=self.headers)

        self.assertEqual(0, len(products))

    def test_get_single_product(self):
        self.post_json(self.PATH, self.product_1, headers=self.headers)
        products = self.get_json(self.PATH, headers=self.headers)
        
        path = self.PATH + '/' + products[0]['product_id']
        data = self.get_json(path, headers=self.headers)
        self.assertEqual('network', data['service'])
        self.assertEqual('product-1', data['name'])

    def test_get_products(self):
        self.useFixture(db_fixtures.DatabaseInit(self.conn))
        products = self.get_json(self.PATH, headers=self.headers)

        self.assertEqual(5, len(products))

    def test_get_products_with_params(self):
        self.useFixture(db_fixtures.DatabaseInit(self.conn))
        products = self.get_json(self.PATH, headers=self.headers, service='compute')

        self.assertEqual(2, len(products))
        self.assertEqual('compute', products[0]['service'])
        self.assertEqual('compute', products[1]['service'])

    def test_get_products_sales(self):
        self.useFixture(db_fixtures.DatabaseInit(self.conn))
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))
        path = self.PATH + '/sales'
        sales = self.get_json(path, headers=self.headers)

        self.assertEqual(5, len(sales['sales']))
        self.assertEqual('0.3013', sales['total_price'])

        add_up = decimal.Decimal('0')

        for s in sales['sales']:
            add_up += decimal.Decimal(s['total_price'])

        self.assertEqual(decimal.Decimal(sales['total_price']), add_up)

    def test_get_single_product_sales(self):
        self.useFixture(db_fixtures.DatabaseInit(self.conn))
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))
        products = self.get_json(self.PATH, headers=self.headers,
                                 service='network')

        # check the router product
        path = self.PATH + '/' + products[0]['product_id']+'/sales'
        sales = self.get_json(path, headers=self.headers)

        self.assertEqual(1, len(sales))
        self.assertEqual('0.0500', sales[0]['total_price'])
        self.assertEqual(1, sales[0]['quantity'])
