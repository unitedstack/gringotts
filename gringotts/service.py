import os
import eventlet
import socket
import sys

from oslo.config import cfg

from gringotts.openstack.common import gettextutils
from gringotts.openstack.common import log
from gringotts.openstack.common import importutils
from gringotts.openstack.common import rpc


LOG = log.getLogger(__name__)

cfg.CONF.register_opts([
    cfg.StrOpt('host',
               default=socket.gethostname(),
               help='Name of this node.  This can be an opaque identifier.  '
               'It is not necessarily a hostname, FQDN, or IP address. '
               'However, the node name must be valid within '
               'an AMQP key, and if using ZeroMQ, a valid '
               'hostname, FQDN, or IP address'),
])


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


def prepare_service(argv=None):
    eventlet.monkey_patch()
    gettextutils.install('gringotts', lazy=False)
    # Override the default control_exchange, default is 'openstack'
    rpc.set_defaults(control_exchange='gringotts')
    cfg.set_defaults(log.log_opts,
                     default_log_levels=['amqplib=WARN',
                                         'qpid.messaging=INFO',
                                         'sqlalchemy=WARN',
                                         'keystoneclient=INFO',
                                         'stevedore=INFO',
                                         'eventlet.wsgi.server=WARN'
                                         ])
    if argv is None:
        argv = sys.argv
    cfg.CONF(argv[1:], project='gringotts')
    log.setup('gringotts')

    #NOTE(suo): Import services/submodules to register methods
    # If use `from gringotts.services import *` will cause SynaxWarning,
    # so we import every submodule implicitly.
    from gringotts import services
    for m in services.SUBMODULES:
        importutils.import_module("gringotts.services.%s" % m)
    LOG.warn('Loaded resources: %s' % services.RESOURCE_GET_MAP.keys())
