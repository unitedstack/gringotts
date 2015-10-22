
import six

from gringotts import exception
from gringotts.openstack.common import jsonutils
from gringotts import utils as gringutils


quantize_decimal = gringutils._quantize_decimal


def calculate_unit_price(quantity, unit_price):
    return int(quantity) * quantize_decimal(unit_price)


def calculate_segmented_price(quantity, price_list):
    """Calculate segmented price of quantity.

    Segmented pricing calculated using a descendent list which has
    elements of the form:
        [(quantity_level)int, (unit_price)str]

    :param quantity: quantity of item
    :param price_list: a list contains segmented pricing data
    :returns: Decimal -- price of quantity of items
    """

    q = int(quantity)
    total_price = quantize_decimal(0)
    for p in price_list:
        if q > p[0]:
            total_price += (q - p[0]) * quantize_decimal(p[1])
            q = p[0]

    return total_price


def calculate_price(quantity, unit_price, price_data=None):
    """Calculate price of quantity of items.

    Calculate price of quantity of items by following order:
        segmented pricing -> unit pricing

    :param quantity: quantity of items
    :unit_price: unit price of item
    :price_data: extra price data of item
    """
    if price_data and not isinstance(price_data, dict):
        raise exception.InvalidParameterValue('price_data should be a dict')

    if price_data and 'type' in price_data:
        base_price = quantize_decimal(price_data.get('base_price', 0))

        if (price_data['type'] == 'segmented') and (
                'segmented' in price_data):
            segmented_price = calculate_segmented_price(
                quantity, price_data['segmented'])

            return segmented_price + base_price

    return calculate_unit_price(quantity, unit_price)


def validate_segmented_price(price_data):
    if ('segmented' not in price_data) or (
            not isinstance(price_data['segmented'], list)):
        raise exception.InvalidParameterValue(
            'No segmented price list in price data')

    price_list = price_data['segmented']
    # Check if item in price_list is valid
    # valid price item if of the form:
    #     [(quantity_level)int, (unit_price)str]
    item_is_valid = all(
        ((len(p) == 2) and (
            isinstance(p[0], int) and (
                isinstance(p[1], six.text_type) and (
                    quantize_decimal(p[1]) >= 0
                )
            )
        )) for p in price_list
    )
    if not item_is_valid:
        raise exception.InvalidParameterValue(
            'Segmented price list has invalid price item')

    # Check if price list has duplicate items
    duplicated = False
    quantity_items = {}
    for p in price_list:
        if p[0] not in quantity_items:
            quantity_items[p[0]] = 1
        else:
            duplicated = True
            break
    if duplicated:
        raise exception.InvalidParameterValue(
            'Segmented price list has duplicate items')

    # Sort price list
    sorted_price_list = sorted(
        price_list, key=lambda p: p[0], reverse=True)

    # Check the price list starts from 0
    if sorted_price_list[-1][0] != 0:
        raise exception.InvalidParameterValue(
            'Number of resource should start from 0')

    return sorted_price_list


def validate_base_price(price_data):
    if 'base_price' not in price_data:
        return '0'

    base_price = price_data['base_price']
    if not isinstance(base_price, six.text_type):
        raise exception.InvalidParameterValue(
            err='Invalid base price type, should be string')
    base_price_decimal = quantize_decimal(base_price)
    if base_price_decimal < 0:
        raise exception.InvalidParameterValue(
            err='Base price should not be negative')
    return str(base_price_decimal)


def validate_price_data(price_data):
    if 'type' not in price_data:
        raise exception.InvalidParameterValue('Not type found in price data')

    new_price_data = {'type': price_data['type']}
    if price_data['type'] == 'segmented':
        new_price_data['segmented'] = validate_segmented_price(price_data)
    else:
        raise exception.InvalidParameterValue('Unsupported pricing type')

    new_price_data['base_price'] = validate_base_price(price_data)

    return new_price_data


def get_price_data(extra, method=None):
    if not extra:
        return None

    extra_data = jsonutils.loads(extra)
    if not method or method == 'hour':
        return extra_data.get('price', None)
    elif method == 'month':
        return extra_data.get('monthly_price', None)
    elif method == 'year':
        return extra_data.get('yearly_price', None)


def rate_limit_to_unit(rate_limit):
    rate_limit = int(rate_limit)
    if rate_limit < 0:
        raise exception.InvalidParameterValue(
            'rate limit should greater than')
    if rate_limit < 1024:
        return 1
    else:
        return int(rate_limit / 1024)
