import eventlet
import sys
import socket

from oslo.config import cfg

from gringotts.openstack.common import gettextutils
from gringotts.openstack.common import log
from gringotts.openstack.common import rpc


cfg.CONF.register_opts([
    cfg.StrOpt('host',
               default=socket.gethostname(),
               help='Name of this node.  This can be an opaque identifier.  '
               'It is not necessarily a hostname, FQDN, or IP address. '
               'However, the node name must be valid within '
               'an AMQP key, and if using ZeroMQ, a valid '
               'hostname, FQDN, or IP address'),
])


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
