#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys
import calendar
from dateutil import tz
from decimal import Decimal, ROUND_HALF_UP
from oslo.config import cfg
from gringotts import constants as const
from random import Random


OPTS = [
    cfg.IntOpt('liner_step',
               default=1,
               help='The step used by liner method'),
    cfg.StrOpt('reserved_method',
               default='liner',
               help='Method of calculate owed days'),
    cfg.DictOpt('discount',
                default={'10': '0',
                         '500': '0.1',
                         '1000': '0.2',
                         '5000': '0.3',
                         '10000': '0.4'}),
]

CONF = cfg.CONF
CONF.register_opts(OPTS)


def _quantize_decimal(value):
    if isinstance(value, Decimal):
        return value.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)


def next_month_days(year, month):
    year += month / 12
    month = month % 12 + 1
    return calendar.monthrange(year, month)[1]


def import_class(import_str):
    """Returns a class from a string including module and class."""
    mod_str, _sep, class_str = import_str.rpartition('.')
    __import__(mod_str)
    return getattr(sys.modules[mod_str], class_str)


def _cal_by_liner(level):
    step = cfg.CONF.liner_step
    return level * step


def _cal_by_mapping(level):
    mapping = {
        '0': 0,
        '1': 1,
        '2': 2,
        '3': 3,
        '4': 4,
        '5': 5,
        '6': 6,
        '7': 7,
        '8': 8,
    }
    return mapping[level]


CAL_METHOD_MAP = {
    'liner': _cal_by_liner,
    'mapping': _cal_by_mapping,
}


def cal_reserved_days(level):
    method = CAL_METHOD_MAP[cfg.CONF.reserved_method]
    return method(level)


def format_datetime(dt):
    return '%s %s.000000' % (dt[:10], dt[11:19])


STATE_MAPPING = {
    'ACTIVE': const.STATE_RUNNING,
    'active': const.STATE_RUNNING,
    'available': const.STATE_RUNNING,
    'in-use': const.STATE_RUNNING,
    'deprecated': const.STATE_RUNNING,
    'DOWN': const.STATE_RUNNING,
    'SHUTOFF': const.STATE_STOPPED,
    'SUSPENDED': const.STATE_SUSPEND,
    'PAUSED': const.STATE_SUSPEND,
    'True': const.STATE_RUNNING,
    'False': const.STATE_STOPPED,
}


def transform_status(status):
    try:
        return STATE_MAPPING[status]
    except KeyError:
        return const.STATE_ERROR


def utc_to_local(utc_dt):
    from_zone = tz.tzutc()
    to_zone = tz.tzlocal()
    return utc_dt.replace(tzinfo=from_zone).astimezone(to_zone).replace(tzinfo=None)


def random_str(randomlength=16):
    str = ''
    chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    length = len(chars) - 1
    random = Random()
    for i in range(randomlength):
        str+=chars[random.randint(0, length)]
    return str


def calculate_bonus(value):
    discount = cfg.CONF.discount
    discount = sorted(discount.iteritems(), key=lambda x:int(x[0]))
    for key, item in discount:
        if value < Decimal(key):
            return value * Decimal(item)
    return 0


def version_api(url, version=None):
    if url is None:
        return url

    if url.endswith('/v1'):
        url = url.replace('/v1', '/')
    elif url.endswith('/v2'):
        url = url.replace('/v2', '/')

    if version is None:
        return url + 'v2'
    else:
        version = "v%s" % version[-1]
        return url + version
