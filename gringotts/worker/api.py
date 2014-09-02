"""Handles all requests to the worker service"""

from oslo.config import cfg

from gringotts.worker import rpcapi
from gringotts.worker import httpapi
from gringotts.worker import service

from gringotts.openstack.common import log as logging

LOG = logging.getLogger(__name__)


class LocalAPI(object):
    """A local version of the worker API that handles all requests
    instead of via RPC
    """

    def __init__(self):
        self._service = service.WorkerService()

    def create_bill(self, ctxt, order_id, action_time=None, remarks=None, end_time=None):
        return self._service.create_bill(ctxt, order_id, action_time=action_time,
                                         remarks=remarks, end_time=end_time)

    def close_bill(self, ctxt, order_id, action_time):
        return self._service.close_bill(ctxt, order_id, action_time)

    def destory_resource(self, ctxt, order_id):
        self._service.destory_resource(ctxt, order_id)

    def create_subscription(self, ctxt, order_id, type=None, **kwargs):
        return self._service.create_subscription(ctxt, order_id,
                                                 type=type, **kwargs)

    def change_subscription(self, ctxt, order_id, quantity, change_to):
        self._service.change_subscription(ctxt, order_id, quantity, change_to)

    def change_flavor_subscription(self, ctxt, order_id,
                                   new_flavor, old_flavor,
                                   service, region_id, change_to):
        self._service.change_flavor_subscription(ctxt, order_id,
                                                 new_flavor, old_flavor,
                                                 service, region_id, change_to)

    def create_order(self, ctxt, order_id, region_id, unit_price, unit, **kwargs):
        self._service.create_order(ctxt, order_id, region_id,
                                   unit_price, unit, **kwargs)

    def change_order(self, ctxt, order_id, change_to, cron_time=None,
                     change_order_status=True, first_change_to=None):
        """first_change_to is used when instance is stopped"""
        self._service.change_order(ctxt, order_id, change_to, cron_time=cron_time,
                                   change_order_status=change_order_status,
                                   first_change_to=first_change_to)

    def get_orders(self, ctxt, status=None, project_id=None, owed=None, region_id=None):
        return self._service.get_orders(ctxt,
                                        status=status,
                                        project_id=project_id,
                                        owed=owed,
                                        region_id=region_id)

    def get_active_orders(self, ctxt, project_id=None, owed=None, charged=None,
                          region_id=None):
        return self._service.get_active_orders(ctxt,
                                               project_id=project_id,
                                               owed=owed,
                                               charged=charged,
                                               region_id=region_id)

    def get_active_order_count(self, ctxt, region_id=None, owed=None):
        return self._service.get_active_order_count(ctxt,
                                                    region_id=region_id,
                                                    owed=owed)

    def get_stopped_order_count(self, ctxt, region_id=None, owed=None):
        return self._service.get_stopped_order_count(ctxt,
                                                     region_id=region_id,
                                                     owed=owed)

    def get_order_by_resource_id(self, ctxt, resource_id):
        return self._service.get_order_by_resource_id(ctxt, resource_id)

    def reset_charged_orders(self, ctxt, order_ids):
        self._service.reset_charged_orders(ctxt, order_ids)

    def create_account(self, ctxt, user_id, project_id, balance,
                       consumption, currency, level, **kwargs):
        self._service.create_account(ctxt, user_id, project_id,
                                     balance, consumption, currency,
                                     level, **kwargs)

    def get_accounts(self, ctxt, owed=None):
        return self._service.get_accounts(ctxt, owed=owed)

    def get_account(self, ctxt, project_id):
        return self._service.get_account(ctxt, project_id)

    def charge_account(self, ctxt, project_id, value, type, come_from):
        self._service.charge_account(ctxt, project_id, value, type, come_from)

    def fix_order(self, ctxt, order_id):
        self._service.fix_order(ctxt, order_id)


class RPCAPI(LocalAPI):
    """A rpc version of the worker API that handles all requests.
    """

    def __init__(self):
        self._service = rpcapi.WorkerAPI()

    def wait_until_ready(self, context, early_timeout=10, early_attempts=10):
        pass


class HTTPAPI(LocalAPI):
    """Http version of the worker api that handles all requests
    """

    def __init__(self):
        self._service = httpapi.WorkerAPI()
