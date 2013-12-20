import datetime
from oslo.config import cfg
from stevedore import extension

from gringotts import db
from gringotts import exception
from gringotts.db import models as db_models

from gringotts.service import prepare_service
from gringotts.openstack.common import log
from gringotts.openstack.common import uuidutils
from gringotts.openstack.common import service as os_service
from gringotts.openstack.common.rpc import service as rpc_service


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

    def _get_timedelta(self, period):
        if period == 'hourly':
            return datetime.timedelta(hours=1)
        elif period == 'dayly':
            return datetime.timedelta(days=1)
        elif period == 'monthly':
            return datetime.timedelta(weeks=4)
        elif period == 'yearly':
            return datetime.timedelta(weeks=48)

    def create_bill(self, message, subscription, product, remarks):

        user_id = message['payload']['user_id']
        fee = product.price

        # Confirm the user's balance is enough
        try:
            account = self.db_conn.get_account(None, user_id)
        except Exception:
            LOG.waring('Fail to find the account: %s' % user_id)
            raise exception.DBError(reason='Fail to find the account')

        if account.balance < fee:
            LOG.waring("The balance of the account(%s) is not enough to"
                       "pay for the bill: %s" % (user_id, bill.as_dict()))
            # NOTE(suo): If the balance is not enough, we should stop
            # the resource, but for now, just raise NotSufficientFund
            # exception.
            raise exception.NotSufficientFund(user_id=user_id)

        # Confirm the resource is health

        # Create a bill
        bill_id = uuidutils.generate_uuid()
        start_time = message['payload']['launched_at']
        end_time = start_time + self._get_timedelta(product.period)
        price = product.price
        unit = product.unit
        subscription_id = subscription.subscription_id
        remarks = remarks
        project_id = message['payload']['project_id']

        bill = db_models.Bill(bill_id, start_time, end_time, fee, price,
                              unit, subscription_id, remarks, user_id,
                              project_id)
        try:
            self.db_conn.create_bill(None, bill)
        except Exception:
            LOG.exception('Fail to create bill: %s' % bill.as_dict())
            raise exception.DBError(reason='Fail to create bill')

        # Update the subscription
        subscription.current_fee += fee
        try:
            sub = self.db_conn.update_subscription(None, subscription)
        except Exception:
            LOG.waring('Fail to update the subscription: %s' % subscription_id)
            raise exception.DBError(reason='Fail to update the subscription')

        # Update the account
        account.balance -= fee
        account.consumption += fee
        try:
            account = self.db_conn.update_account(None, account)
        except Exception:
            LOG.waring('Fail to update the account: %s' % user_id)
            raise exception.DBError(reason='Fail to update the account')

    def pre_deduct(self, ctxt, values):
        LOG.debug('%s, you are here' % values)

def worker():
    prepare_service()
    os_service.launch(WorkerService()).wait()
