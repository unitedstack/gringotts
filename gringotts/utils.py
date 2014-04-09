#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys
import calendar
from decimal import Decimal, ROUND_HALF_UP
from oslo.config import cfg
from gringotts import constants as const


OPTS = [
    cfg.IntOpt('liner_step',
               default=1,
               help='The step used by liner method'),
    cfg.StrOpt('reserved_method',
               default='liner',
               help='Method of calculate owed days'),
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
    'DOWN': const.STATE_RUNNING,
    'SHUTOFF': const.STATE_STOPPED,
    'SUSPENDED': const.STATE_SUSPEND,
    'PAUSED': const.STATE_SUSPEND,
}


def transform_status(status):
    try:
        return STATE_MAPPING[status]
    except KeyError:
        return const.STATE_ERROR
