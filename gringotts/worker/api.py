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

    def update_bill(self, ctxt, order_id):
        return self._service.update_bill(ctxt, order_id)

    def close_bill(self, ctxt, order_id, action_time):
        return self._service.close_bill(ctxt, order_id, action_time)

    def destory_resource(self, ctxt, order_id):
        self._service.destory_resource(ctxt, order_id)

    def get_product(self, ctxt, product_name, service, region_id):
        return self._service.get_product(ctxt, product_name, service, region_id)

    def create_subscription(self, ctxt, order_id, type=None, **kwargs):
        return self._service.create_subscription(ctxt, order_id,
                                                 type=type, **kwargs)

    def get_subscriptions(self, ctxt, order_id=None, type=None):
        return self._service.get_subscriptions(ctxt,
                                               order_id=order_id,
                                               type=type)

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

    def get_orders(self, ctxt, status=None, project_id=None, owed=None, region_id=None, type=None):
        return self._service.get_orders(ctxt,
                                        status=status,
                                        project_id=project_id,
                                        owed=owed,
                                        region_id=region_id,
                                        type=type)

    def get_active_orders(self, ctxt, user_id=None, project_id=None, owed=None, charged=None,
                          region_id=None):
        return self._service.get_active_orders(ctxt,
                                               user_id=user_id,
                                               project_id=project_id,
                                               owed=owed,
                                               charged=charged,
                                               region_id=region_id)

    def get_active_order_count(self, ctxt, region_id=None, owed=None, type=None):
        return self._service.get_active_order_count(ctxt,
                                                    region_id=region_id,
                                                    owed=owed,
                                                    type=type)

    def get_stopped_order_count(self, ctxt, region_id=None, owed=None, type=None):
        return self._service.get_stopped_order_count(ctxt,
                                                     region_id=region_id,
                                                     owed=owed,
                                                     type=type)

    def get_order_by_resource_id(self, ctxt, resource_id):
        return self._service.get_order_by_resource_id(ctxt, resource_id)

    def get_order(self, ctxt, order_id):
        return self._service.get_order(ctxt, order_id)

    def reset_charged_orders(self, ctxt, order_ids):
        self._service.reset_charged_orders(ctxt, order_ids)

    def create_account(self, ctxt, user_id, domain_id, balance, consumption, level,
                       **kwargs):
        self._service.create_account(ctxt, user_id, domain_id, balance, consumption,
                                     level, **kwargs)

    def get_accounts(self, ctxt, owed=None):
        return self._service.get_accounts(ctxt, owed=owed)

    def get_account(self, ctxt, user_id):
        return self._service.get_account(ctxt, user_id)

    def charge_account(self, ctxt, user_id, value, type, come_from):
        self._service.charge_account(ctxt, user_id, value, type, come_from)

    def create_project(self, ctxt, user_id, project_id, domain_id, consumption):
        self._service.create_project(ctxt, user_id, project_id, domain_id, consumption)

    def get_projects(self, ctxt, user_id=None, type=None):
        return self._service.get_projects(ctxt, user_id=user_id, type=type)

    def delete_resources(self, ctxt, project_id, region_name=None):
        return self._service.delete_resources(ctxt, project_id,
                                              region_name=region_name)

    def get_resources(self, ctxt, project_id, region_name=None):
        return self._service.get_resources(ctxt, project_id,
                                           region_name=region_name)

    def change_billing_owner(self, ctxt, project_id, user_id):
        return self._service.change_billing_owner(ctxt, project_id, user_id)

    def fix_order(self, ctxt, order_id):
        self._service.fix_order(ctxt, order_id)

    def create_deduct(self, ctxt, user_id, money, type="1", remark=None, req_id=None, **kwargs):
        self._service.create_deduct(ctxt, user_id, money, type=type, remark=remark, req_id=req_id, **kwargs)

    def deduct_external_account(self, ctxt, user_id, money, type="1", remark=None, req_id=None, **kwargs):
        self._service.deduct_external_account(ctxt, user_id, money, type=type, remark=remark, req_id=req_id, **kwargs)

    def get_external_balance(self, ctxt, user_id):
        return self._service.get_external_balance(ctxt, user_id)

    def get_orders_summary(self, ctxt, user_id, start_time, end_time):
        return self._service.get_orders_summary(ctxt, user_id, start_time, end_time)

    def get_charges(self, ctxt, user_id):
        return self._service.get_charges(ctxt, user_id)

    def get_consumption_per_day(self, ctxt, user_id):
        return self._service.get_consumption_per_day(ctxt, user_id)


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

    def __init__(self, *args, **kwargs):
        self._service = httpapi.WorkerAPI(*args, **kwargs)
