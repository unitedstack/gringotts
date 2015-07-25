
import testtools

from gringotts import exception
from gringotts.price import pricing
from gringotts.tests import core as tests
from gringotts.tests import utils as test_utils


class PricingTestCase(tests.TestCase):

    def setUp(self):
        super(PricingTestCase, self).setUp()

    def test_calculate_unit_price(self):
        unit_price = '0.2'

        quantity_list = [1, 2]
        expected_list = ['0.2', '0.4']

        for q, p in zip(quantity_list, expected_list):
            price = pricing.calculate_unit_price(q, unit_price)
            self.assertEqual(self.quantize(p), price)

    def test_calculate_segmented_price(self):
        price_list = [[10, '0.1'], [4, '0.2'], [0, '0.3']]

        quantity_list = [1, 4, 5, 10, 11]
        expected_list = ['0.3', '1.2', '1.4', '2.4', '2.5']

        for q, p in zip(quantity_list, expected_list):
            price = pricing.calculate_segmented_price(q, price_list)
            self.assertEqual(self.quantize(p), price)

    def test_calculate_price_using_unit_price(self):
        unit_price = '0.2'

        quantity_list = [1, 2]
        expected_list = ['0.2', '0.4']

        for q, p in zip(quantity_list, expected_list):
            price = pricing.calculate_price(q, unit_price)
            self.assertEqual(self.quantize(p), price)

    def test_calculate_price_using_segmented_price(self):
        unit_price = '0.2'
        price_data = test_utils.PricingTestMixin.build_segmented_price_data(
            '0.0', [[10, '0.1'], [4, '0.2'], [0, '0.3']])

        quantity_list = [1, 4, 5, 10, 11]
        expected_list = ['0.3', '1.2', '1.4', '2.4', '2.5']

        for q, p in zip(quantity_list, expected_list):
            price = pricing.calculate_price(q, unit_price, price_data)
            self.assertEqual(self.quantize(p), price)

    def test_calculate_price_using_base_price_and_segmented_price(self):
        unit_price = '0.2'
        price_data = test_utils.PricingTestMixin.build_segmented_price_data(
            '5.0', [[10, '0.1'], [4, '0.2'], [0, '0.3']])

        quantity_list = [1, 4, 5, 10, 11]
        expected_list = ['5.3', '6.2', '6.4', '7.4', '7.5']

        for q, p in zip(quantity_list, expected_list):
            price = pricing.calculate_price(q, unit_price, price_data)
            self.assertEqual(self.quantize(p), price)


class ItemUnitTestCase(tests.TestCase):

    def setUp(self):
        super(ItemUnitTestCase, self).setUp()

    def test_rate_limit_to_unit(self):
        to_unit = pricing.rate_limit_to_unit
        self.assertEqual(1, to_unit(1023))
        self.assertEqual(1, to_unit(1024))
        self.assertEqual(1, to_unit(1025))
        self.assertEqual(2, to_unit(2048))
        with testtools.ExpectedException(exception.InvalidParameterValue):
            self.assertEqual(1, to_unit(-1))
        with testtools.ExpectedException(ValueError):
            self.assertEqual(1, to_unit('a'))
