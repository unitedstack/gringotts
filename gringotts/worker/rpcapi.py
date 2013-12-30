from oslo.config import cfg

from gringotts.openstack.common import log
from gringotts.openstack.common.rpc import proxy


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

    def create_bill(self, ctxt, order_id, action_time, remarks):
        return self.call(ctxt,
                         self.make_msg('create_bill',
                                       order_id=order_id,
                                       action_time=action_time,
                                       remarks=remarks))

    def pre_deduct(self, ctxt, order_id):
        return self.call(ctxt,
                         self.make_msg('pre_deduct',
                                       order_id=order_id))

    def close_bill(self, ctxt, order_id, action_time):
        return self.call(ctxt,
                         self.make_msg('close_bill',
                                       order_id=order_id,
                                       action_time=action_time))
