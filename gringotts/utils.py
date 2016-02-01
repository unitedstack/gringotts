#!/usr/bin/python
# -*- coding: utf-8 -*-
import bisect
import datetime
import hashlib
import six
import struct
import sys
import calendar

from dateutil import tz
from dateutil.relativedelta import relativedelta
from decimal import Decimal, ROUND_HALF_UP
from oslo_config import cfg
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


def to_months(method, period):
    if method == 'month':
        return period
    elif method == 'year':
        return period * 12
    raise ValueError("method should be month or year")


def add_months(source_datetime, months):
    return source_datetime + relativedelta(months=months)


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
    chars = 'ABCDEFGHIJKLMNPQRSTUVWXY13456789'
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


def smart_str(s, encoding='utf-8', strings_only=False, errors='strict'):
    """Returns a bytestring version of 's', encoded as specified in 'encoding'.

    If strings_only is True, don't convert (some) non-string-like objects.
    """
    if strings_only and isinstance(s, (types.NoneType, int)):
        return s
    if not isinstance(s, basestring):
        try:
            return str(s)
        except UnicodeEncodeError:
            if isinstance(s, Exception):
                # An Exception subclass containing non-ASCII data that doesn't
                # know how to print itself properly. We shouldn't raise a
                # further exception.
                return ' '.join([smart_str(arg, encoding, strings_only,
                        errors) for arg in s])
            return unicode(s).encode(encoding, errors)
    elif isinstance(s, unicode):
        return s.encode(encoding, errors)
    elif s and encoding != 'utf-8':
        return s.decode('utf-8', errors).encode(encoding, errors)
    else:
        return s


class HashRing(object):

    def __init__(self, nodes, replicas=100):
        self._ring = dict()
        self._sorted_keys = []

        for node in nodes:
            for r in six.moves.range(replicas):
                hashed_key = self._hash('%s-%s' % (node, r))
                self._ring[hashed_key] = node
                self._sorted_keys.append(hashed_key)
        self._sorted_keys.sort()

    @staticmethod
    def _hash(key):
        return struct.unpack_from('>I',
                                  hashlib.md5(smart_str(key)).digest())[0]

    def _get_position_on_ring(self, key):
        hashed_key = self._hash(key)
        position = bisect.bisect(self._sorted_keys, hashed_key)
        return position if position < len(self._sorted_keys) else 0

    def get_node(self, key):
        if not self._ring:
            return None
        pos = self._get_position_on_ring(key)
        return self._ring[self._sorted_keys[pos]]


def true_or_false(abool):
    if isinstance(abool, bool):
        return abool
    elif isinstance(abool, six.string_types):
        abool = abool.lower()
        if abool == 'true':
            return True
        if abool == 'false':
            return False
    raise ValueError("should be bool or true/false string")


def normalize_timedelta(duration):
    if not duration:
        return
    unit = duration[-1]
    value = duration[:-1]
    if unit == 'm':
        return datetime.timedelta(minutes=float(value))
    if unit == 'h':
        return datetime.timedelta(hours=float(value))
    if unit == 'd':
        return datetime.timedelta(days=float(value))
    raise ValueError("unsupport time unit")
