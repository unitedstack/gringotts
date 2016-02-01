import functools
import inspect
import logging as log

from decimal import Decimal
from oslo_config import cfg

from gringotts.client import client
from gringotts.exception import GringottsException


LOG = log.getLogger(__name__)


def wrap_exception(exc_type=None, with_raise=True):
    """ Wrap exception around resource method

    This decorator wraps a method to catch any exceptions that may get thrown.
    It logs the exception, and may sends message to notification system.

    In every normal situation, there will not exception be raised. When it requests
    a non-exists resource, it will return None instead of exception. Only when any of the services
    is not avaliable, it will raise an exception to stop the further execution.
    """
    def inner(f):
        def wrapped(uuid, *args, **kwargs):
            try:
                if exc_type == 'delete' or exc_type == 'stop':
                    gclient = client.get_client()
                    order = gclient.get_order_by_resource_id(uuid)
                    account = gclient.get_account(order['user_id'])
                    if (order['unit'] == 'hour' and
                        order['owed'] and
                        account['owed'] and
                        Decimal(str(account['balance'])) < 0 and
                        int(account['level']) != 9) or (
                        order['unit'] in ['month', 'year'] and
                        order['owed']):
                        LOG.warn("The resource: %s is indeed owed, can be execute"
                                 "the action: %s", uuid, f.__name__)
                        return f(uuid, *args, **kwargs)
                    else:
                        LOG.warn("The resource: %s is not owed, should not execute"
                                 "the action: %s", uuid, f.__name__)
                else:
                    return f(uuid, *args, **kwargs)
            except Exception as e:
                msg = None
                if exc_type == 'single' or exc_type == 'delete' or exc_type == 'stop':
                    msg = 'Fail to do %s for resource: %s, reason: %s' % (f.__name__, uuid, e)
                elif exc_type == 'bulk':
                    msg = 'Fail to do %s for account: %s, reason: %s' % (f.__name__, uuid, e)
                elif exc_type == 'list':
                    msg = 'Fail to do %s for account: %s, reason: %s' % (f.__name__, uuid, e)
                elif exc_type == 'get':
                    msg = 'Fail to do %s for resource: %s, reason: %s' % (f.__name__, uuid, e)
                elif exc_type == 'put':
                    msg = 'Fail to do %s for resource: %s, reason: %s' % (f.__name__, uuid, e)
                else:
                    msg = 'Fail to do %s, reason: %s' % (f.__name__, e)
                if with_raise:
                    raise GringottsException(message=msg)
                else:
                    LOG.error(msg)
        return functools.wraps(f)(wrapped)
    return inner


RESOURCE_LIST_METHOD = []
RESOURCE_DELETE_METHOD = []

RESOURCE_GET_MAP = {}
RESOURCE_STOPPED_STATE = {}
DELETE_METHOD_MAP = {}
STOP_METHOD_MAP = {}
RESOURCE_CREATE_MAP = {}


def register(ks_client, service=None, resource=None, mtype=None,
             stopped_state=None, function_available=None,
             *args, **kwargs):
    def inner(f):
        def wrapped(uuid, *args, **kwargs):
            return f(uuid, *args, **kwargs)

        is_available = True
        if callable(function_available):
            is_available = function_available(*args, **kwargs)

        services = ks_client.get_services()

        if service in services and is_available:
            if mtype == 'list':
                RESOURCE_LIST_METHOD.append(f)
            elif mtype == 'deletes':
                RESOURCE_DELETE_METHOD.append(f)
            elif mtype == 'get':
                RESOURCE_GET_MAP[resource] = f
                RESOURCE_STOPPED_STATE[resource] = stopped_state
            elif mtype == 'delete':
                DELETE_METHOD_MAP[resource] = f
            elif mtype == 'stop':
                STOP_METHOD_MAP[resource] = f
        return functools.wraps(f)(wrapped)
    return inner


def register_class(ks_client, service, resource, cls):
    if not inspect.isclass(cls):
        raise ValueError('Only classes may be registered.')

    services = ks_client.get_services()
    if service in services:
        if resource not in RESOURCE_CREATE_MAP:
            RESOURCE_CREATE_MAP[resource] = cls()


class Resource(object):
    def __init__(self, id, name, resource_type, is_bill=True,
                 status=None, original_status=None, **kwargs):
        self.id = id
        self.name = name
        self.resource_type = resource_type
        self.is_bill = is_bill
        self.status = status
        self.original_status = original_status

        self.fields = list(kwargs)
        self.fields.extend(['id', 'name', 'resource_type', 'is_bill',
                            'status', 'original_status'])

        for k, v in kwargs.iteritems():
            setattr(self, k, v)

    def as_dict(self):
        d = {}
        for f in self.fields:
            v = getattr(self, f)
            d[f] = v
        return d

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __getitem__(self, key):
        return getattr(self, key)

    def __repr__(self):
        return '%s: %s: %s' % (self.resource_type, self.name, self.id)

    def __eq__(self, other):
        return self.id == other.id and self.original_status == other.original_status


SUBMODULES  = [
    'ceilometer',
    'cinder',
    'glance',
    'keystone',
    'manila',
    'neutron',
    'nova',
]
