
from decimal import Decimal

from gringotts import exception
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
    for p in sorted(price_list, key=lambda p: p['count'], reverse=True):
        if q > p['count']:
            total_price += (q - p['count']) * quantize_decimal(p['price'])
            q = p['count']

    return total_price


def calculate_price(quantity, price_data=None):
    """Calculate price of quantity of items.

    Calculate price of quantity of items by following order:
        segmented pricing -> unit pricing

    :param quantity: quantity of items
    :price_data: unit_price data of item
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
            isinstance(p['count'], int) and (
                isinstance(p['price'], Decimal) and (
                    quantize_decimal(p['price']) >= 0
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
        if p['count'] not in quantity_items:
            quantity_items[p['count']] = 1
        else:
            duplicated = True
            break
    if duplicated:
        raise exception.InvalidParameterValue(
            'Segmented price list has duplicate items')

    # Sort price list
    sorted_price_list = sorted(
        price_list, key=lambda p: p['count'], reverse=True)

    # Check the price list starts from 0
    if sorted_price_list[-1]['count'] != 0:
        raise exception.InvalidParameterValue(
            'Number of resource should start from 0')

    return sorted_price_list


def validate_base_price(price_data):
    if 'base_price' not in price_data:
        return '0'

    base_price = price_data['base_price']
    if not isinstance(base_price, Decimal):
        raise exception.InvalidParameterValue(
            err='Invalid base price type, should be decimal')
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


def get_price_data(unit_price, method=None):
    if not unit_price:
        return None

    if not method or method == 'hour':
        return unit_price.get('price', None)
    elif method == 'month':
        return unit_price.get('monthly_price', None)
    elif method == 'year':
        return unit_price.get('yearly_price', None)


def rate_limit_to_unit(rate_limit):
    rate_limit = int(rate_limit)
    if rate_limit < 0:
        raise exception.InvalidParameterValue(
            'rate limit should greater than 0')
    if rate_limit < 1024:
        return 1
    else:
        return int(rate_limit / 1024)
