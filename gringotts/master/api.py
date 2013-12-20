"""Handles all requests to the master service"""

from oslo.config import cfg

from gringotts.master import service
from gringotts.master import rpcapi

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

    def resource_created(self, ctxt, message, subscription, product):
        self._service.instance_created(ctxt, message, subscription, product)


class API(LocalAPI):
    """Master API that handles requests via RPC to the MasterService
    """

    def __init__(self):
        self._service = rpcapi.MasterAPI()

    def wait_until_ready(self, context, early_timeout=10, early_attempts=10):
        pass
