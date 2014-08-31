import sys
from oslo.config import cfg
from gringotts.worker import api as worker_api


worker_opts = [
    cfg.StrOpt('protocol',
                default='local',
                help="The protocol that worker works, three options:"
                     "local, http, rpc"),
]

cfg.CONF(sys.argv[1:], project='gringotts')

worker_group = cfg.OptGroup(name='worker')
CONF = cfg.CONF
CONF.register_group(worker_group)
CONF.register_opts(worker_opts, worker_group)


def API(*args, **kwargs):
    protocol = cfg.CONF.worker.protocol
    if protocol == 'local':
        api = worker_api.LocalAPI
    elif protocol == 'rpc':
        api = worker_api.RPCAPI
    elif protocol == 'http':
        api = worker_api.HTTPAPI
    return api(*args, **kwargs)
