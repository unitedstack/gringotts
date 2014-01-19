import datetime
from oslo.config import cfg
from decimal import Decimal, ROUND_HALF_UP

from gringotts import context
from gringotts import db
from gringotts.db import models as db_models
from gringotts import exception

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
        super(WorkerService, self).__init__(*args, **kwargs)

    def start(self):
        super(WorkerService, self).start()
        # Add a dummy thread to have wait() working
        self.tg.add_timer(604800, lambda: None)

    def create_bill(self, ctxt, order_id, action_time, remarks):
        # Get the order
        order = self.db_conn.get_order(context.get_admin_context(), order_id)
        LOG.debug('Get the order: %s' % order.as_dict())

        # Convert serialized dict/string to object
        if isinstance(action_time, basestring):
            action_time = timeutils.parse_strtime(action_time,
                                                  fmt=TIMESTAMP_TIME_FORMAT)

        total_price = order.unit_price

        # Confirm the user's balance is enough
        try:
            account = self.db_conn.get_account(context.get_admin_context(),
                                               order.project_id)
        except Exception:
            LOG.warning('Fail to find the account: %s' % order.project_id)
            raise exception.DBError(reason='Fail to find the account')

        if account.balance < total_price:
            LOG.warning("The balance of the account(%s) is not enough to"
                        "pay for the fee: %s" % (order.project_id, total_price))
            # NOTE(suo): If the balance is not enough, we should stop
            # the resource, but for now, just raise NotSufficientFund
            # exception.
            raise exception.NotSufficientFund(project_id=order.project_id)

        LOG.debug('The project(%s)\'s account balance is enough' % order.project_id)

        # Confirm the resource is health
        LOG.debug('Confirm the resource(%s) is health' % order.resource_id)

        # Create a bill
        bill_id = uuidutils.generate_uuid()
        start_time = action_time
        end_time = start_time + datetime.timedelta(hours=1)
        type=order.type
        unit_price = order.unit_price
        unit = order.unit
        order_id = order.order_id
        resource_id = order.resource_id
        remarks = remarks
        user_id = order.user_id
        project_id = order.project_id

        bill = db_models.Bill(bill_id, start_time, end_time, type, unit_price, unit,
                              total_price, order_id, resource_id, remarks, user_id,
                              project_id)
        try:
            self.db_conn.create_bill(context.get_admin_context(), bill)
        except Exception:
            LOG.exception('Fail to create bill: %s' % bill.as_dict())
            raise exception.DBError(reason='Fail to create bill')
        LOG.debug('Created a bill(%s) for the order(%s)' % (bill.as_dict(), order_id))

        # Update the order
        order.total_price += total_price
        order.cron_time = action_time + datetime.timedelta(hours=1)
        order.status = 'active'
        order.updated_at = datetime.datetime.utcnow()
        try:
            self.db_conn.update_order(context.get_admin_context(), order)
        except Exception:
            LOG.warning('Fail to update the order: %s' % order.order_id)
            raise exception.DBError(reason='Fail to update the order')
        LOG.debug('Update the order(%s)' % order_id)

        # Update subscriptions and products' total_price
        subscriptions = self.db_conn.get_subscriptions_by_order_id(
            context.get_admin_context(),
            order.order_id,
            status='active')

        for sub in subscriptions:
            sub_single_price = sub.unit_price * sub.quantity
            sub.total_price += sub_single_price
            sub.updated_at = datetime.datetime.utcnow()
            try:
                self.db_conn.update_subscription(context.get_admin_context(), sub)
            except Exception:
                LOG.error('Fail to update the subscription: %s' % sub.as_dict())
                raise exception.DBError(reason='Fail to update the subscription')

            try:
                product = self.db_conn.get_product(context.get_admin_context(),
                                                   sub.product_id)
                product.total_price += sub_single_price
                self.db_conn.update_product(context.get_admin_context(),
                                            product)
            except Exception:
                LOG.error("Fail to update the product\'s total_price: %s"
                          % sub.as_dict())
                raise exception.DBError(reason='Fail to update the product')
        LOG.debug('Update the subscriptions and products total_price')

        # Update the account
        account.balance -= total_price
        account.consumption += total_price
        account.updated_at = datetime.datetime.utcnow()
        try:
            account = self.db_conn.update_account(context.get_admin_context(), account)
        except Exception:
            LOG.warning('Fail to update the account: %s' % order.project_id)
            raise exception.DBError(reason='Fail to update the account')
        LOG.debug('Update the account(%s)' % account.as_dict())

    def pre_deduct(self, ctxt, order_id):
        # Get the latest bill
        try:
            bill = self.db_conn.get_latest_bill(context.get_admin_context(),
                                                order_id)
        except Exception:
            LOG.error('Fail to get latest bill belongs to order: %s'
                      % order_id)
            raise exception.LatestBillNotFound(order_id=order_id)

        # If the bill accross a day, we will create a new bill for the order
        if bill.end_time.hour is 0:
            action_time = bill.end_time
            remarks = 'daily billing'
            self.create_bill(ctxt, order_id, action_time, remarks)
            return

        # Get the order
        order = self.db_conn.get_order(context.get_admin_context(), order_id)
        LOG.debug('Get the order: %s' % order.as_dict())

        total_price = order.unit_price

        # Confirm the user's balance is enough
        try:
            account = self.db_conn.get_account(context.get_admin_context(),
                                               order.project_id)
        except Exception:
            LOG.warning('Fail to find the account: %s' % order.project_id)
            raise exception.DBError(reason='Fail to find the account')

        if account.balance < total_price:
            LOG.warning("The balance of the account(%s) is not enough to"
                        "pay for the fee: %s" % (order.project_id, total_price))
            # NOTE(suo): If the balance is not enough, we should stop
            # the resource, but for now, just raise NotSufficientFund
            # exception.
            raise exception.NotSufficientFund(project_id=order.project_id)

        LOG.debug('The project(%s)\'s account balance is enough' % order.project_id)

        # Confirm the resource is health
        LOG.debug('Confirm the resource(%s) is health' % order.resource_id)

        # Update the bill
        bill.end_time += datetime.timedelta(hours=1)
        bill.total_price += total_price
        bill.updated_at = datetime.datetime.utcnow()

        try:
            self.db_conn.update_bill(context.get_admin_context(),
                                     bill)
        except Exception:
            LOG.exception('Fail to update bill: %s' % bill.as_dict())
            raise exception.DBError(reason='Fail to update bill')
        LOG.debug('Update the bill(%s)' % bill.as_dict())

        # Update the order
        order.total_price += total_price
        order.cron_time += datetime.timedelta(hours=1)
        order.updated_at = datetime.datetime.utcnow()
        try:
            self.db_conn.update_order(context.get_admin_context(), order)
        except Exception:
            LOG.warning('Fail to update the order: %s' % order.order_id)
            raise exception.DBError(reason='Fail to update the order')
        LOG.debug('Update the order(%s)' % order_id)

        # Update subscriptions
        subscriptions = self.db_conn.get_subscriptions_by_order_id(
            context.get_admin_context(),
            order.order_id,
            status='active')

        for sub in subscriptions:
            sub_single_price = sub.unit_price * sub.quantity
            sub.total_price += sub_single_price
            sub.updated_at = datetime.datetime.utcnow()
            try:
                self.db_conn.update_subscription(context.get_admin_context(), sub)
            except Exception:
                LOG.error('Fail to update the subscription: %s' % sub.as_dict())
                raise exception.DBError(reason='Fail to update the subscription')

            try:
                product = self.db_conn.get_product(context.get_admin_context(),
                                                   sub.product_id)
                product.total_price += sub_single_price
                self.db_conn.update_product(context.get_admin_context(),
                                            product)
            except Exception:
                LOG.error("Fail to update the product\'s total_price: %s"
                          % sub.as_dict())
                raise exception.DBError(reason='Fail to update the product')
        LOG.debug('Update the subscriptions and products total_price')

        # Update the account
        account.balance -= total_price
        account.consumption += total_price
        account.updated_at = datetime.datetime.utcnow()
        try:
            account = self.db_conn.update_account(context.get_admin_context(), account)
        except Exception:
            LOG.warning('Fail to update the account: %s' % order.project_id)
            raise exception.DBError(reason='Fail to update the account')
        LOG.debug('Update the account(%s)' % account.as_dict())

    def close_bill(self, ctxt, order_id, action_time):
        # Get the order
        order = self.db_conn.get_order(context.get_admin_context(), order_id)
        LOG.debug('Get the order: %s' % order.as_dict())

        action_time = timeutils.parse_strtime(action_time,
                                              fmt=TIMESTAMP_TIME_FORMAT)

        # Update the latest bill
        try:
            bill = self.db_conn.get_latest_bill(context.get_admin_context(),
                                                order.order_id)
        except Exception:
            LOG.error('Fail to get latest bill belongs to order: %s'
                      % order.order_id)
            raise exception.LatestBillNotFound(order_id=order.order_id)

        # FIXME(suo): We should ensure delta is greater than 0
        delta = timeutils.delta_seconds(action_time, bill.end_time) / 3600.0
        delta = self._quantize_decimal(delta)

        more_fee = self._quantize_decimal(delta  * order.unit_price)
        bill.end_time = action_time
        bill.total_price -= more_fee
        bill.updated_at = datetime.datetime.utcnow()

        try:
            self.db_conn.update_bill(context.get_admin_context(), bill)
        except Exception:
            LOG.exception('Fail to update bill: %s' % bill.as_dict())
            raise exception.DBError(reason='Fail to update bill')
        LOG.debug('Update the latest bill')

        # Update the order
        order.total_price -= more_fee
        order.cron_time = None
        order.status = 'inactive'
        order.updated_at = datetime.datetime.utcnow()
        try:
            self.db_conn.update_order(context.get_admin_context(), order)
        except Exception:
            LOG.warning('Fail to update the order: %s' % order.order_id)
            raise exception.DBError(reason='Fail to update the order')
        LOG.debug('Update the order')

        # Update subscriptions
        subscriptions = self.db_conn.get_subscriptions_by_order_id(
            context.get_admin_context(),
            order.order_id,
            status='active')

        for sub in subscriptions:
            sub_more_fee = self._quantize_decimal(delta * sub.unit_price * sub.quantity)
            sub.total_price -= sub_more_fee
            sub.status = 'inactive'
            sub.updated_at = datetime.datetime.utcnow()
            try:
                self.db_conn.update_subscription(context.get_admin_context(), sub)
            except Exception:
                LOG.error('Fail to update the subscription: %s' % sub.as_dict())
                raise exception.DBError(reason='Fail to update the subscription')

            try:
                product = self.db_conn.get_product(context.get_admin_context(),
                                                   sub.product_id)
                product.total_price -= sub_more_fee
                self.db_conn.update_product(context.get_admin_context(),
                                            product)
            except Exception:
                LOG.error("Fail to update the product\'s total_price: %s"
                          % sub.as_dict())
                raise exception.DBError(reason='Fail to update the product')
        LOG.debug('Update the subscriptions and products total_price')

        # Update the account
        try:
            account = self.db_conn.get_account(context.get_admin_context(),
                                               order.project_id)
            account.balance += more_fee
            account.consumption -= more_fee
            account = self.db_conn.update_account(context.get_admin_context(),
                                                  account)
        except Exception:
            LOG.warning('Fail to update the account: %s' % order.project_id)
            raise exception.DBError(reason='Fail to update the account')
        LOG.debug('Update the account(%s)' % account.as_dict())

    def _quantize_decimal(self, value):
        if isinstance(value, Decimal):
           return  value.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
        return Decimal(value).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)


def worker():
    prepare_service()
    os_service.launch(WorkerService()).wait()
