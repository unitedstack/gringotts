"""Handles all requests to the worker service"""

from oslo.config import cfg

from gringotts.worker import service
from gringotts.worker import rpcapi

from gringotts.openstack.common import log as logging

worker_opts = [
    cfg.BoolOpt('use_local',
                default=False,
                help='Perform gring-worker operations locally'),
]

worker_group = cfg.OptGroup(name='worker')

CONF = cfg.CONF

CONF.register_group(worker_group)
CONF.register_opts(worker_opts, worker_group)

LOG = logging.getLogger(__name__)


class LocalAPI(object):
    """A local version of the worker API that handles all requests
    instead of via RPC
    """

    def __init__(self):
        self._service = service.WorkerService()

    def pre_charge(self, ctxt, values):
        self._service.pre_charge(ctxt, values)


class API(LocalAPI):
    """Master API that handles requests via RPC to the MasterService
    """

    def __init__(self):
        self._service = rpcapi.WorkerAPI()

    def wait_until_ready(self, context, early_timeout=10, early_attempts=10):
        pass
