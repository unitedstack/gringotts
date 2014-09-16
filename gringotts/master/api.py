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

    def get_cronjob_count(self, ctxt):
        return self._service.get_cronjob_count(ctxt)

    def get_datejob_count(self, ctxt):
        return self._service.get_datejob_count(ctxt)

    def get_datejob_count_30_days(self, ctxt):
        return self._service.get_datejob_count_30_days(ctxt)

    def resource_created(self, ctxt, order_id, action_time, remarks):
        self._service.resource_created(ctxt, order_id, action_time, remarks)

    def resource_created_again(self, ctxt, order_id, action_time, remarks):
        self._service.resource_created_again(ctxt, order_id, action_time, remarks)

    def resource_deleted(self, ctxt, order_id, action_time, remarks):
        self._service.resource_deleted(ctxt, order_id, action_time, remarks)

    def resource_changed(self, ctxt, order_id, action_time, change_to, remarks):
        self._service.resource_changed(ctxt, order_id, action_time,
                                       change_to, remarks)

    def resource_resized(self, ctxt, order_id, action_time, quantity, remarks):
        self._service.resource_resized(ctxt, order_id, action_time,
                                       quantity, remarks)

    def instance_stopped(self, ctxt, order_id, action_time):
        self._service.instance_stopped(ctxt, order_id, action_time)

    def instance_resized(self, ctxt, order_id, action_time,
                         new_flavor, old_flavor,
                         service, region_id, remarks):
        self._service.instance_resized(ctxt, order_id, action_time,
                                       new_flavor, old_flavor,
                                       service, region_id, remarks)

    def clean_date_jobs(self, ctxt, resource_ids):
        self._service.clean_date_jobs(ctxt, resource_ids)


class API(LocalAPI):
    """Master API that handles requests via RPC to the MasterService
    """

    def __init__(self):
        self._service = rpcapi.MasterAPI()

    def wait_until_ready(self, context, early_timeout=10, early_attempts=10):
        pass
