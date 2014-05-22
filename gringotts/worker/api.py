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

    def create_bill(self, ctxt, order_id, action_time=None, remarks=None):
        return self._service.create_bill(ctxt, order_id, action_time=action_time,
                                         remarks=remarks)

    def close_bill(self, ctxt, order_id, action_time):
        return self._service.close_bill(ctxt, order_id, action_time)

    def destory_resource(self, ctxt, order_id):
        self._service.destory_resource(ctxt, order_id)

    def create_subscription(self, ctxt, order_id, type=None, **kwargs):
        return self._service.create_subscription(ctxt, order_id,
                                                 type=type, **kwargs)

    def change_subscription(self, ctxt, order_id, quantity, change_to):
        self._service.change_subscription(ctxt, order_id, quantity, change_to)

    def create_order(self, ctxt, order_id, region_id, unit_price, unit, **kwargs):
        self._service.create_order(ctxt, order_id, region_id,
                                   unit_price, unit, **kwargs)

    def change_order(self, ctxt, order_id, change_to):
        self._service.change_order(ctxt, order_id, change_to)

    def get_orders(self, ctxt, status=None, project_id=None, owed=None, region_id=None):
        return self._service.get_orders(ctxt,
                                        status=status,
                                        project_id=project_id,
                                        owed=owed,
                                        region_id=region_id)

    def get_active_orders(self, ctxt, project_id=None, owed=None, region_id=None):
        return self._service.get_active_orders(ctxt,
                                               project_id=project_id,
                                               owed=owed,
                                               region_id=region_id)

    def get_active_order_count(self, ctxt, region_id=None, owed=None):
        return self._service.get_active_order_count(ctxt,
                                                    region_id=region_id,
                                                    owed=owed)

    def get_order_by_resource_id(self, ctxt, resource_id):
        return self._service.get_order_by_resource_id(ctxt, resource_id)

    def create_account(self, ctxt, user_id, project_id, balance,
                       consumption, currency, level, **kwargs):
        self._service.create_account(ctxt, user_id, project_id,
                                     balance, consumption, currency,
                                     level, **kwargs)

    def get_accounts(self, ctxt):
        return self._service.get_accounts(ctxt)


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
