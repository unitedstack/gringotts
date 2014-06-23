import os
import functools
from oslo.config import cfg
from gringotts.openstack.common import log


LOG = log.getLogger(__name__)


OPTS = [
    cfg.StrOpt('os_username',
               default=os.environ.get('OS_USERNAME', 'admin'),
               help='Username to use for openstack service access'),
    cfg.StrOpt('os_password',
               default=os.environ.get('OS_PASSWORD', 'admin'),
               help='Password to use for openstack service access'),
    cfg.StrOpt('os_tenant_name',
               default=os.environ.get('OS_TENANT_NAME', 'admin'),
               help='Tenant name to use for openstack service access'),
    cfg.StrOpt('os_endpoint_type',
               default=os.environ.get('OS_ENDPOINT_TYPE', 'admin'),
               help='Type of endpoint in Identity service catalog to use for '
                    'communication with OpenStack services.'),
    cfg.StrOpt('user_domain_name',
               default='Default',
               help='user domain name'),
    cfg.StrOpt('project_domain_name',
               default='Default',
               help='project domain name'),
    cfg.StrOpt('os_auth_url',
               default=os.environ.get('OS_AUTH_URL',
                                      'http://localhost:35357/v3'),
               help='Auth URL to use for openstack service access')
]

cfg.CONF.register_opts(OPTS, group="service_credentials")


def wrap_exception(exc_type=None):
    """This decorator wraps a method to catch any exceptions that may
    get thrown. It logs the exception, and may sends message to notification
    system.
    """
    def inner(f):
        def wrapped(uuid, *args, **kwargs):
            try:
                return f(uuid, *args, **kwargs)
            except Exception as e:
                msg = None
                result = True
                if exc_type == 'single':
                    msg = 'Fail to do %s for resource: %s, reason: %s' % (f.__name__, uuid, e)
                elif exc_type == 'bulk':
                    msg = 'Fail to do %s for account: %s, reason: %s' % (f.__name__, uuid, e)
                elif exc_type == 'list':
                    msg = 'Fail to do %s for account: %s, reason: %s' % (f.__name__, uuid, e)
                    result = []
                elif exc_type == 'get':
                    msg = 'Fail to do %s for resource: %s, reason: %s' % (f.__name__, uuid, e)
                    result = None
                LOG.error(msg)
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
