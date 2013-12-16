from oslo.config import cfg

from gringotts.openstack.common.rpc import proxy
from gringotts.openstack.common import log


LOG = log.getLogger(__name__)


rpcapi_opts = [
    cfg.StrOpt('worker_topic',
               default='gringotts.worker',
               help='the topic worker listen on')
]

cfg.CONF.register_opts(rpcapi_opts, group='worker')


class WorkerAPI(proxy.RpcProxy):
    BASE_RPC_VERSION = '1.0'

    def __init__(self):
        super(WorkerAPI, self).__init__(
            topic=cfg.CONF.worker.worker_topic,
            default_version=self.BASE_RPC_VERSION)

    def pre_charge(self, ctxt, values):
        return self.call(ctxt, self.make_msg('pre_charge', values=values))
