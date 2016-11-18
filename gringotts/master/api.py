"""Handles all requests to the master service"""

from oslo_config import cfg

from gringotts.master import rpcapi
from gringotts.master import service


master_opts = [
    cfg.BoolOpt('use_local',
                default=False,
                help='Perform gring-master operations locally'),
]

master_group = cfg.OptGroup(name='master')

CONF = cfg.CONF

CONF.register_group(master_group)
CONF.register_opts(master_opts, master_group)


class LocalAPI(object):
    """A local version of the master API that handles all requests
    instead of via RPC
    """

    def __init__(self):
        self._service = service.MasterService()

    def create_monthly_job(self, ctxt, order_id, run_date):
        self._service.create_monthly_job(ctxt, order_id, run_date)

    def change_monthly_job_time(self, ctxt, order_id, run_date,
                                clear_date_jobs=None):
        self._service.change_monthly_job_time(ctxt, order_id, run_date,
                                              clear_date_jobs=clear_date_jobs)

    def delete_sched_jobs(self, ctxt, order_id):
        self._service.delete_sched_jobs(ctxt, order_id)

    def get_apsched_jobs_count(self, ctxt):
        return self._service.get_apsched_jobs_count(ctxt)

    def resource_created(self, ctxt, order_id, action_time, remarks):
        self._service.resource_created(ctxt, order_id, action_time, remarks)

    def resource_created_again(self, ctxt, order_id, action_time, remarks):
        self._service.resource_created_again(ctxt, order_id, action_time, remarks)

    def resource_started(self, ctxt, order_id, action_time, remarks):
        self._service.resource_started(ctxt, order_id, action_time, remarks)

    def resource_stopped(self, ctxt, order_id, action_time, remarks):
        self._service.resource_stopped(ctxt, order_id, action_time, remarks)

    def resource_deleted(self, ctxt, order_id, action_time, remarks):
        self._service.resource_deleted(ctxt, order_id, action_time, remarks)

    def resource_changed(self, ctxt, order_id, action_time, change_to, remarks):
        self._service.resource_changed(ctxt, order_id, action_time,
                                       change_to, remarks)

    def resource_resized(self, ctxt, order_id, action_time, quantity, remarks):
        self._service.resource_resized(ctxt, order_id, action_time,
                                       quantity, remarks)

    def resource_restore(self, ctxt, order_id, action_time, remarks):
        self._service.resource_restore(ctxt, order_id, action_time, remarks)

    def instance_stopped(self, ctxt, order_id, action_time):
        self._service.instance_stopped(ctxt, order_id, action_time)

    def instance_resized(self, ctxt, order_id, action_time,
                         new_flavor, old_flavor,
                         service, region_id, remarks):
        self._service.instance_resized(ctxt, order_id, action_time,
                                       new_flavor, old_flavor,
                                       service, region_id, remarks)


class API(LocalAPI):
    """Master API that handles requests via RPC to the MasterService
    """

    def __init__(self):
        self._service = rpcapi.MasterAPI()

    def wait_until_ready(self, context, early_timeout=10, early_attempts=10):
        pass
