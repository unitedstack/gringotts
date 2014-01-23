import datetime
from oslo.config import cfg
from decimal import Decimal, ROUND_HALF_UP

from gringotts import constants as const
from gringotts import context
from gringotts import db
from gringotts.db import models as db_models
from gringotts import exception
from gringotts import utils as gringutils

from gringotts.openstack.common import log
from gringotts.openstack.common.rpc import service as rpc_service
from gringotts.openstack.common import service as os_service
from gringotts.openstack.common import timeutils
from gringotts.openstack.common import uuidutils

from gringotts.service import prepare_service


TIMESTAMP_TIME_FORMAT = '%Y-%m-%d %H:%M:%S.%f'

LOG = log.getLogger(__name__)

OPTS = []

cfg.CONF.register_opts(OPTS, group="worker")

cfg.CONF.import_opt('worker_topic', 'gringotts.worker.rpcapi',
                    group='worker')


class WorkerService(rpc_service.Service):

    def __init__(self, *args, **kwargs):
        kwargs.update(
            host=cfg.CONF.host,
            topic=cfg.CONF.worker.worker_topic,
        )
        self.db_conn = db.get_connection(cfg.CONF)
        self.ctxt = context.get_admin_context()
        super(WorkerService, self).__init__(*args, **kwargs)

    def start(self):
        super(WorkerService, self).start()
        # Add a dummy thread to have wait() working
        self.tg.add_timer(604800, lambda: None)

    def _update_account(self, project_id, total_price):
        """Update the project_id's account
        """
        try:
            account = self.db_conn.get_account(self.ctxt, project_id)
        except Exception:
            LOG.warning('Fail to find the account: %s' % project_id)
            raise exception.DBError(reason='Fail to find the account')

        # Update the account
        account.balance -= total_price
        account.consumption += total_price
        account.updated_at = datetime.datetime.utcnow()
        try:
            account = self.db_conn.update_account(self.ctxt, account)
        except Exception:
            LOG.warning('Fail to update the account: %s' % order.project_id)
            raise exception.DBError(reason='Fail to update the account')
        LOG.debug('Update the account(%s)' % account.as_dict())

    def _update_subscriptions(self, order, duration):
        """Update subscriptions and products' total_price
        """
        subscriptions = self.db_conn.get_subscriptions_by_order_id(
            self.ctxt,
            order.order_id,
            type=order.status)

        for sub in subscriptions:
            sub_single_price = sub.unit_price * sub.quantity * duration
            sub_single_price = gringutils._quantize_decimal(sub_single_price)
            sub.total_price += sub_single_price
            sub.updated_at = datetime.datetime.utcnow()
            try:
                self.db_conn.update_subscription(self.ctxt, sub)
            except Exception:
                LOG.error('Fail to update the subscription: %s' % sub.as_dict())
                raise exception.DBError(reason='Fail to update the subscription')

            try:
                product = self.db_conn.get_product(self.ctxt, sub.product_id)
                product.total_price += sub_single_price
                self.db_conn.update_product(self.ctxt, product)
            except Exception:
                LOG.error("Fail to update the product\'s total_price: %s"
                          % sub.as_dict())
                raise exception.DBError(reason='Fail to update the product')
        LOG.debug('Update the subscriptions and products total_price')

    def _update_order(self, order, total_price, cron_time):
        """Update the order's total_price and cron_time
        """
        order.total_price += total_price
        order.cron_time = cron_time
        order.updated_at = datetime.datetime.utcnow()
        try:
            self.db_conn.update_order(self.ctxt, order)
        except Exception:
            LOG.warning('Fail to update the order: %s' % order.order_id)
            raise exception.DBError(reason='Fail to update the order')
        LOG.debug('Update the order(%s)' % order.order_id)

    def _create_bill(self, order, action_time, remarks, status=None):
        # Create an owed bill
        bill_id = uuidutils.generate_uuid()
        start_time = action_time
        end_time = start_time + datetime.timedelta(hours=1)
        type = order.type
        status = status
        unit_price = order.unit_price
        unit = order.unit
        total_price = order.unit_price
        order_id = order.order_id
        resource_id = order.resource_id
        remarks = remarks
        user_id = order.user_id
        project_id = order.project_id

        bill = db_models.Bill(bill_id, start_time, end_time, type, status,
                              unit_price, unit, total_price, order_id,
                              resource_id, remarks, user_id, project_id)
        try:
            self.db_conn.create_bill(self.ctxt, bill)
        except Exception:
            LOG.exception('Fail to create bill: %s' % bill.as_dict())
            raise exception.DBError(reason='Fail to create bill')
        LOG.debug('Created a bill(%s) for the order(%s)' % (bill.as_dict(), order_id))

    def _get_latest_bill(self, order_id):
        """Get the latest bill
        """
        try:
            bill = self.db_conn.get_latest_bill(self.ctxt, order_id)
        except Exception:
            LOG.error('Fail to get latest bill belongs to order: %s'
                      % order_id)
            raise exception.LatestBillNotFound(order_id=order_id)
        return bill

    def _get_owed_bills(self, order_id):
        """Get owed bills of the order
        """
        try:
            bills = self.db_conn.get_owed_bills(self.ctxt, order_id)
        except Exception:
            LOG.error('Fail to get owed bills belongs to order: %s'
                      % order_id)
            raise exception.OwedBillsNotFound(order_id=order_id)
        return bills

    def _update_bill(self, bill):
        try:
            self.db_conn.update_bill(self.ctxt, bill)
        except Exception:
            LOG.exception('Fail to update bill: %s' % bill.as_dict())
            raise exception.DBError(reason='Fail to update bill')
        LOG.debug('Update the bill(%s)' % bill.as_dict())

    def _get_order(self, order_id):
        # Get the order
        order = self.db_conn.get_order(self.ctxt, order_id)
        LOG.debug('Get the order: %s' % order.as_dict())
        return order

    def create_bill(self, ctxt, order_id, action_time, remarks):
        # Get the order
        order = self._get_order(order_id)

        # Convert serialized dict/string to object
        if isinstance(action_time, basestring):
            action_time = timeutils.parse_strtime(action_time,
                                                  fmt=TIMESTAMP_TIME_FORMAT)
        self._create_bill(order, action_time, remarks, status=const.BILL_PAYED)

        cron_time = action_time + datetime.timedelta(hours=1)
        self._update_order(order, order.unit_price, cron_time)

        self._update_subscriptions(order, 1)
        self._update_account(order.project_id, order.unit_price)

    def pre_deduct(self, ctxt, order_id):
        # Get the latest bill
        bill = self._get_latest_bill(order_id)

        # If the bill accross a day, we will create a new bill for the order
        if bill.end_time.hour is 0:
            action_time = bill.end_time
            remarks = 'Daily Billing'
            self.create_bill(ctxt, order_id, action_time, remarks)
            return

        # Get the order
        order = self._get_order(order_id)

        # Update the bill
        bill.end_time += datetime.timedelta(hours=1)
        bill.total_price += order.unit_price
        bill.updated_at = datetime.datetime.utcnow()
        self._update_bill(bill)

        cron_time = order.cron_time + datetime.timedelta(hours=1)
        self._update_order(order, order.unit_price, cron_time)

        self._update_subscriptions(order, 1)
        self._update_account(order.project_id, order.unit_price)

    def close_bill(self, ctxt, order_id, action_time):
        # Get the order
        order = self._get_order(order_id)

        if isinstance(action_time, basestring):
            action_time = timeutils.parse_strtime(action_time,
                                                  fmt=TIMESTAMP_TIME_FORMAT)

        # Update the latest bill
        bill = self._get_latest_bill(order_id)

        # FIXME(suo): We should ensure delta is greater than 0
        delta = timeutils.delta_seconds(action_time, bill.end_time) / 3600.0
        delta = gringutils._quantize_decimal(delta)

        more_fee = gringutils._quantize_decimal(delta * order.unit_price)
        bill.end_time = action_time
        bill.total_price -= more_fee
        bill.updated_at = datetime.datetime.utcnow()
        self._update_bill(bill)

        # Update the order
        order.total_price -= more_fee
        order.cron_time = None
        order.updated_at = datetime.datetime.utcnow()
        try:
            self.db_conn.update_order(self.ctxt, order)
        except Exception:
            LOG.warning('Fail to update the order: %s' % order.order_id)
            raise exception.DBError(reason='Fail to update the order')
        LOG.debug('Update the order')

        # Update subscriptions
        subscriptions = self.db_conn.get_subscriptions_by_order_id(
            self.ctxt,
            order.order_id,
            type=order.status)

        for sub in subscriptions:
            sub_more_fee = gringutils._quantize_decimal(delta * sub.unit_price * sub.quantity)
            sub.total_price -= sub_more_fee
            sub.updated_at = datetime.datetime.utcnow()
            try:
                self.db_conn.update_subscription(self.ctxt, sub)
            except Exception:
                LOG.error('Fail to update the subscription: %s' % sub.as_dict())
                raise exception.DBError(reason='Fail to update the subscription')

            try:
                product = self.db_conn.get_product(self.ctxt, sub.product_id)
                product.total_price -= sub_more_fee
                self.db_conn.update_product(self.ctxt, product)
            except Exception:
                LOG.error("Fail to update the product\'s total_price: %s"
                          % sub.as_dict())
                raise exception.DBError(reason='Fail to update the product')
        LOG.debug('Update the subscriptions and products total_price')

        # Update the account
        try:
            account = self.db_conn.get_account(self.ctxt, order.project_id)
            account.balance += more_fee
            account.consumption -= more_fee
            account = self.db_conn.update_account(self.ctxt, account)
        except Exception:
            LOG.warning('Fail to update the account: %s' % order.project_id)
            raise exception.DBError(reason='Fail to update the account')
        LOG.debug('Update the account(%s)' % account.as_dict())

    def _quantize_decimal(self, value):
        if isinstance(value, Decimal):
           return  value.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
        return Decimal(value).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)

    def destory_resource(self, ctxt, order_id):
        LOG.debug('Destroy the resource because of owed')


def worker():
    prepare_service()
    os_service.launch(WorkerService()).wait()
