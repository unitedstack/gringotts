from oslo.config import cfg

from gringotts.openstack.common import log
from gringotts.openstack.common.rpc import proxy


LOG = log.getLogger(__name__)


rpcapi_opts = [
    cfg.StrOpt('master_topic',
               default='gringotts.master',
               help='the topic master listen on')
]

cfg.CONF.register_opts(rpcapi_opts, group='master')


class MasterAPI(proxy.RpcProxy):
    BASE_RPC_VERSION = '1.0'

    def __init__(self):
        super(MasterAPI, self).__init__(
            topic=cfg.CONF.master.master_topic,
            default_version=self.BASE_RPC_VERSION)

    def resource_created(self, ctxt, subscriptions, action_time, remarks):
        return self.call(ctxt,
                         self.make_msg('resource_created',
                                       subscriptions=subscriptions,
                                       action_time=action_time,
                                       remarks=remarks))

    def resource_deleted(self, ctxt, subscriptions, action_time):
        return self.call(ctxt,
                         self.make_msg('resource_deleted',
                                       subscriptions=subscriptions,
                                       action_time=action_time))

    def resource_changed(self, ctxt, subscriptions, action_time, remarks):
        return self.call(ctxt,
                         self.make_msg('resource_changed',
                                       subscriptions=subscriptions,
                                       action_time=action_time,
                                       remarks=remarks))
