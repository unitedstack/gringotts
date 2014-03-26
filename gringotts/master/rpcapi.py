from oslo.config import cfg

from gringotts.openstack.common import log
from gringotts.openstack.common.rpc import proxy


LOG = log.getLogger(__name__)

cfg.CONF.import_opt('master_topic', 'gringotts.master.service',
                    group='master')

class MasterAPI(proxy.RpcProxy):
    BASE_RPC_VERSION = '1.0'

    def __init__(self):
        super(MasterAPI, self).__init__(
            topic=cfg.CONF.master.master_topic,
            default_version=self.BASE_RPC_VERSION)

    def resource_created(self, ctxt, order_id, action_time, remarks):
        return self.cast(ctxt,
                         self.make_msg('resource_created',
                                       order_id=order_id,
                                       action_time=action_time,
                                       remarks=remarks))

    def resource_deleted(self, ctxt, order_id, action_time):
        return self.cast(ctxt,
                         self.make_msg('resource_deleted',
                                       order_id=order_id,
                                       action_time=action_time))

    def resource_changed(self, ctxt, order_id, action_time, change_to, remarks):
        return self.cast(ctxt,
                         self.make_msg('resource_changed',
                                       order_id=order_id,
                                       action_time=action_time,
                                       change_to=change_to,
                                       remarks=remarks))

    def resource_resized(self, ctxt, order_id, action_time, quantity, remarks):
        return self.cast(ctxt,
                         self.make_msg('resource_resized',
                                       order_id=order_id,
                                       action_time=action_time,
                                       quantity=quantity,
                                       remarks=remarks))
