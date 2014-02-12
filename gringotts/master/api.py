"""Handles all requests to the master service"""

from oslo.config import cfg

from gringotts.master import rpcapi
from gringotts.master import service

from gringotts.openstack.common import log as logging

master_opts = [
    cfg.BoolOpt('use_local',
                default=False,
                help='Perform gring-master operations locally'),
]

master_group = cfg.OptGroup(name='master')

CONF = cfg.CONF

CONF.register_group(master_group)
CONF.register_opts(master_opts, master_group)

LOG = logging.getLogger(__name__)


class LocalAPI(object):
    """A local version of the master API that handles all requests
    instead of via RPC
    """

    def __init__(self):
        self._service = service.MasterService()

    def resource_created(self, ctxt, order_id, action_time, remarks):
        self._service.resource_created(ctxt, order_id, action_time, remarks)

    def resource_deleted(self, ctxt, order_id, action_time):
        self._service.resource_deleted(ctxt, order_id, action_time)

    def resource_changed(self, ctxt, order_id, action_time, change_to, remarks):
        self._service.resource_changed(ctxt, order_id, action_time,
                                       change_to, remarks)

    def resource_resized(self, ctxt, order_id, action_time, quantity, remarks):
        self._service.resource_resized(ctxt, order_id, action_time,
                                       quantity, remarks)



class API(LocalAPI):
    """Master API that handles requests via RPC to the MasterService
    """

    def __init__(self):
        self._service = rpcapi.MasterAPI()

    def wait_until_ready(self, context, early_timeout=10, early_attempts=10):
        pass
