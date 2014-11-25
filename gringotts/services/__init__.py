import functools
from decimal import Decimal
from oslo.config import cfg

from gringotts import context
from gringotts import worker
from gringotts.openstack.common import log


LOG = log.getLogger(__name__)


def wrap_exception(exc_type=None):
    """This decorator wraps a method to catch any exceptions that may
    get thrown. It logs the exception, and may sends message to notification
    system.
    """
    def inner(f):
        def wrapped(uuid, *args, **kwargs):
            try:
                if exc_type == 'delete' or exc_type == 'stop':
                    worker_api = worker.API()
                    order = worker_api.get_order_by_resource_id(context.get_admin_context(),
                                                                uuid)
                    account = worker_api.get_account(context.get_admin_context(),
                                                     order['user_id'])
                    if order['owed'] and account['owed'] and Decimal(str(account['balance'])) < 0 and int(account['level']) < 9:
                        LOG.warn('The resource: %s is indeed owed, can be execute the action: %s' % \
                                (uuid, f.__name__))
                        return f(uuid, *args, **kwargs)
                    else:
                        LOG.warn('The resource: %s is not owed, should not execute the action: %s' % \
                                (uuid, f.__name__))
                else:
                    return f(uuid, *args, **kwargs)
            except Exception as e:
                msg = None
                result = True
                if exc_type == 'single' or exc_type == 'delete' or exc_type == 'stop':
                    msg = 'Fail to do %s for resource: %s, reason: %s' % (f.__name__, uuid, e)
                elif exc_type == 'bulk':
                    msg = 'Fail to do %s for account: %s, reason: %s' % (f.__name__, uuid, e)
                elif exc_type == 'list':
                    msg = 'Fail to do %s for account: %s, reason: %s' % (f.__name__, uuid, e)
                    result = []
                elif exc_type == 'get':
                    msg = 'Fail to do %s for resource: %s, reason: %s' % (f.__name__, uuid, e)
                    result = None
                LOG.exception(msg)
                return result
        return functools.wraps(f)(wrapped)
    return inner


wrap_exception = functools.partial(wrap_exception, exc_type='single')


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
