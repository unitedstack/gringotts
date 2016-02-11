import os
import eventlet
import socket
import sys

from oslo_config import cfg

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
    cfg.IntOpt('checker_workers',
               default=1,
               help='Number of workers for checker service. A single worker is '
               'enabled by default'),
    cfg.IntOpt('master_workers',
               default=1,
               help='Number of workers for master service. A single worker is '
               'enabled by default')
])

cfg.CONF.import_group("keystone_authtoken", "keystonemiddleware.auth_token")


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
