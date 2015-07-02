from oslo.config import cfg

from gringotts import context
from gringotts import db
from gringotts import utils
from gringotts.db import models as db_models
from gringotts import exception

from gringotts.openstack.common import log
from gringotts.openstack.common.rpc import service as rpc_service
from gringotts.openstack.common import service as os_service
from gringotts.openstack.common import timeutils

from gringotts.service import prepare_service


TIMESTAMP_TIME_FORMAT = '%Y-%m-%d %H:%M:%S.%f'
LOG = log.getLogger(__name__)


class WorkerService(rpc_service.Service):
    """Worker execute commands from other components via db_conn or http.
    There is no logical in worker, it is just a worker that do jobs. The
    logical is in master and waiter.
    """

    def __init__(self, *args, **kwargs):
        kwargs.update(
            host=cfg.CONF.host,
            topic=cfg.CONF.worker.worker_topic,
        )
        self.ctxt = context.get_admin_context()
        self.db_conn = db.get_connection(cfg.CONF)
        super(WorkerService, self).__init__(*args, **kwargs)

    def start(self):
        super(WorkerService, self).start()
        # Add a dummy thread to have wait() working
        self.tg.add_timer(604800, lambda: None)

    def create_bill(self, ctxt, order_id, action_time=None, remarks=None, end_time=None):
        if isinstance(action_time, basestring):
            action_time = timeutils.parse_strtime(action_time,
                                                  fmt=TIMESTAMP_TIME_FORMAT)
        if isinstance(end_time, basestring):
            end_time = timeutils.parse_strtime(end_time,
                                               fmt=TIMESTAMP_TIME_FORMAT)
        try:
            result = self.db_conn.create_bill(ctxt, order_id, action_time=action_time,
                                              remarks=remarks, end_time=end_time)
            LOG.debug('Create bill for order %s successfully.' % order_id)
            return result
        except Exception:
            LOG.exception('Fail to create bill for the order: %s' % order_id)
            raise exception.BillCreateFailed(order_id=order_id)

    def close_bill(self, ctxt, order_id, action_time):
        if isinstance(action_time, basestring):
            action_time = timeutils.parse_strtime(action_time,
                                                  fmt=TIMESTAMP_TIME_FORMAT)
        try:
            result = self.db_conn.close_bill(ctxt, order_id, action_time)
            LOG.debug('Close bill for order %s successfully.' % order_id)
            return result
        except Exception:
            LOG.exception('Fail to close bill for the order: %s' % order_id)
            raise exception.BillCloseFailed(order_id=order_id)

    def destory_resource(self, ctxt, order_id):
        LOG.debug('Destroy the resource because of owed')

    def get_product(self, ctxt, product_name, service, region_id):
        filters = dict(name=product_name,
                       service=service,
                       region_id=region_id)
        ps = list(self.db_conn.get_products(ctxt, filters=filters))
        if ps:
            return ps[0]
        return None

    def create_subscription(self, ctxt, order_id, type=None, **kwargs):
        sub = dict(order_id=order_id,
                   type=type,
                   **kwargs)
        return self.db_conn.create_subscription(ctxt, **sub)

    def get_subscriptions(self, ctxt, order_id=None, type=None):
        LOG.warn("Not Implemented, use http protocol")

    def change_subscription(self, ctxt, order_id, quantity, change_to):
        kwargs = dict(order_id=order_id,
                      quantity=quantity,
                      change_to=change_to)
        self.db_conn.update_subscription(ctxt, **kwargs)

    def change_flavor_subscription(self, ctxt, order_id,
                                   new_flavor, old_flavor,
                                   service, region_id, change_to):
        kwargs = dict(order_id=order_id,
                      new_flavor=new_flavor,
                      old_flavor=old_flavor,
                      service=service,
                      region_id=region_id,
                      change_to=change_to)
        self.db_conn.update_flavor_subscription(ctxt, **kwargs)

    def create_order(self, ctxt, order_id, region_id, unit_price, unit, **kwargs):
        order = dict(order_id=order_id,
                     region_id=region_id,
                     unit_price=unit_price,
                     unit=unit,
                     **kwargs)
        self.db_conn.create_order(ctxt, **order)

    def change_order(self, ctxt, order_id, change_to, cron_time=None,
                     change_order_status=True, first_change_to=None):
        kwargs = dict(order_id=order_id,
                      change_to=change_to,
                      cron_time=cron_time,
                      change_order_status=change_order_status,
                      first_change_to=first_change_to)
        self.db_conn.update_order(ctxt, **kwargs)

    def get_orders(self, ctxt, status=None, project_id=None, owed=None, region_id=None, type=None):
        return self.db_conn.get_orders(ctxt, status=status,
                                       project_id=project_id,
                                       type=type,
                                       owed=owed,
                                       region_id=region_id)

    def get_active_orders(self, ctxt, user_id=None, project_id=None, owed=None, charged=None,
                          region_id=None):
        return self.db_conn.get_active_orders(ctxt,
                                              user_id=user_id,
                                              project_id=project_id,
                                              owed=owed,
                                              charged=charged,
                                              region_id=region_id)

    def get_active_order_count(self, ctxt, region_id=None, owed=None, type=None):
        return self.db_conn.get_active_order_count(ctxt,
                                                   region_id=region_id,
                                                   owed=owed,
                                                   type=type)

    def get_stopped_order_count(self, ctxt, region_id=None, owed=None, type=None):
        return self.db_conn.get_stopped_order_count(ctxt,
                                                    region_id=region_id,
                                                    owed=owed,
                                                    type=type)

    def get_order_by_resource_id(self, ctxt, resource_id):
        return self.db_conn.get_order_by_resource_id(ctxt, resource_id)

    def reset_charged_orders(self, ctxt, order_ids):
        try:
            self.db_conn.reset_charged_orders(ctxt, order_ids)
        except Exception:
            LOG.exception("Fail to reset charged orders: %s" % data.order_ids)

    def create_account(self, ctxt, user_id, domain_id, balance,
                       consumption, level, **kwargs):
        try:
            account = db_models.Account(user_id, domain_id, balance,
                                        consumption, level, **kwargs)
            self.db_conn.create_account(ctxt, account)
        except Exception:
            LOG.exception('Fail to create account %s for the domain %s' % \
                    (user_id, domain_id))
            raise exception.AccountCreateFailed(user_id=user_id, domain_id=domain_id)

    def get_accounts(self, ctxt, owed=None):
        return self.db_conn.get_accounts(ctxt, owed=owed)

    def get_account(self, ctxt, project_id):
        return self.db_conn.get_account(ctxt, project_id)

    def charge_account(self, ctxt, user_id, value, type, come_from):
        if isinstance(value, basestring):
            value = utils._quantize_decimal(value)
        try:
            self.db_conn.update_account(ctxt, user_id,
                                        value=value,
                                        type=type,
                                        come_from=come_from)
        except Exception:
            LOG.exception('Fail to charge the account: %s, charge(%s, %s, %s)' % \
                    (user_id, value, type, come_from))
            raise exception.AccountChargeFailed(value=value, user_id=user_id)

    def create_project(self, ctxt, user_id, project_id, domain_id, consumption):
        project = db_models.Project(user_id, project_id, domain_id, consumption)
        self.db_conn.create_project(ctxt, project)

    def get_projects(self, ctxt, user_id=None, type=None):
        LOG.warn("Not Implemented, use http protocol")

    def delete_resources(self, ctxt, project_id, region_name=None):
        LOG.warn("Not Implemented, use http protocol")

    def get_resources(self, ctxt, project_id, region_name=None):
        LOG.warn("Not Implemented, use http protocol")

    def change_billing_owner(self, ctxt, project_id, user_id):
        self.db_conn.change_billing_owner(ctxt,
                                          project_id=project_id,
                                          user_id=user_id)

    def fix_order(self, ctxt, order_id):
        self.db_conn.fix_order(ctxt, order_id)

    def create_deduct(self, ctxt, user_id, money, type="1", remark=None, req_id=None, **kwargs):
        raise NotImplementedError()

    def deduct_external_account(self, ctxt, user_id, money, type="1", remark=None, req_id=None, **kwargs):
        raise NotImplementedError()

    def get_external_balance(self, ctxt, user_id):
        raise NotImplementedError()

    def get_orders_summary(self, ctxt, user_id, start_time, end_time):
        raise NotImplementedError()

    def get_charges(self, ctxt, user_id):
        raise NotImplementedError()

    def get_consumption_per_day(self, ctxt, user_id):
        raise NotImplementedError()


def worker():
    prepare_service()
    os_service.launch(WorkerService()).wait()
