from oslo.config import cfg

from gringotts import context
from gringotts import db
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

    def create_bill(self, ctxt, order_id, action_time=None, remarks=None):
        if isinstance(action_time, basestring):
            action_time = timeutils.parse_strtime(action_time,
                                                  fmt=TIMESTAMP_TIME_FORMAT)
        try:
            result = self.db_conn.create_bill(ctxt, order_id, action_time=action_time,
                                              remarks=remarks)
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

    def create_subscription(self, ctxt, order_id, type=None, **kwargs):
        sub = dict(order_id=order_id,
                   type=type,
                   **kwargs)
        return self.db_conn.create_subscription(ctxt, **sub)

    def change_subscription(self, ctxt, order_id, quantity, change_to):
        kwargs = dict(order_id=order_id,
                      quantity=quantity,
                      change_to=change_to)
        self.db_conn.update_subscription(ctxt, **kwargs)

    def create_order(self, ctxt, order_id, region_id, unit_price, unit, **kwargs):
        order = dict(order_id=order_id,
                     region_id=region_id,
                     unit_price=unit_price,
                     unit=unit,
                     **kwargs)
        self.db_conn.create_order(ctxt, **order)

    def change_order(self, ctxt, order_id, change_to):
        kwargs = dict(order_id=order_id,
                      change_to=change_to)
        self.db_conn.update_order(ctxt, **kwargs)

    def get_orders(self, ctxt, status=None, project_id=None, owed=None, region_id=None):
        return self.db_conn.get_orders(ctxt, status=status,
                                       project_id=project_id,
                                       owed=owed,
                                       region_id=region_id)

    def get_active_orders(self, ctxt, project_id=None, owed=None, region_id=None):
        return self.db_conn.get_active_orders(ctxt,
                                              project_id=project_id,
                                              owed=owed,
                                              region_id=region_id)

    def get_active_order_count(self, ctxt, region_id=None, owed=None):
        return self.db_conn.get_active_order_count(ctxt,
                                                   region_id=region_id,
                                                   owed=owed)

    def get_order_by_resource_id(self, ctxt, resource_id):
        return self.db_conn.get_order_by_resource_id(ctxt, resource_id)

    def create_account(self, ctxt, user_id, project_id, balance,
                       consumption, currency, level, **kwargs):
        try:
            account = db_models.Account(user_id, project_id,
                                        balance, consumption, currency,
                                        level, **kwargs)
            self.db_conn.create_account(ctxt, account)
        except Exception:
            LOG.exception('Fail to create account: %s' % account.as_dict())
            raise exception.AccountCreateFailed(project_id=project_id)

    def get_accounts(self, ctxt):
        return self.db_conn.get_accounts(ctxt)


def worker():
    prepare_service()
    os_service.launch(WorkerService()).wait()
