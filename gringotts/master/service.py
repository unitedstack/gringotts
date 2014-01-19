import datetime

from datetime import timedelta
from dateutil import tz

from oslo.config import cfg
from eventlet.green.threading import Lock

from apscheduler.scheduler import Scheduler as APScheduler
from apscheduler.jobstores.shelve_store import ShelveJobStore

from gringotts import context
from gringotts import db
from gringotts.db import models as db_models
from gringotts import worker

from gringotts.openstack.common import log
from gringotts.openstack.common.rpc import service as rpc_service
from gringotts.openstack.common import service as os_service
from gringotts.openstack.common import timeutils
from gringotts.service import prepare_service


LOG = log.getLogger(__name__)

TIMESTAMP_TIME_FORMAT = '%Y-%m-%d %H:%M:%S.%f'

OPTS = []

cfg.CONF.register_opts(OPTS, group="master")

cfg.CONF.import_opt('master_topic', 'gringotts.master.rpcapi',
                    group='master')


class MasterService(rpc_service.Service):

    def __init__(self, *args, **kwargs):
        kwargs.update(
            host=cfg.CONF.host,
            topic=cfg.CONF.master.master_topic,
        )
        self.db_conn = db.get_connection(cfg.CONF)
        self.worker_api = worker.API()
        self.apsched = APScheduler()
        self.jobs = {}
        self.lock = Lock()
        super(MasterService, self).__init__(*args, **kwargs)

    def start(self):
        self.apsched.start()
        self.load_jobs()
        super(MasterService, self).start()
        # Add a dummy thread to have wait() working
        self.tg.add_timer(604800, lambda: None)

    def load_jobs(self):
        LOG.debug('Loading jobs before master started')
        orders = self.db_conn.get_orders(context.get_admin_context(),
                                         status='active')
        for order in orders:
            danger_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=30)
            if order.cron_time > danger_time:
                self._create_cron_job(order.order_id,
                                      start_date=order.cron_time)
            else:
                LOG.warning('The order(%s) is in danger time after master started'
                            % order.order_id)
                while order.cron_time <= danger_time:
                    self._pre_deduct(order.order_id)
                    order.cron_time += datetime.timedelta(hours=1)
                self._create_cron_job(order.order_id,
                                      start_date=order.cron_time)

    def _pre_deduct(self, order_id):
        # NOTE(suo): Because account is shared among different cron job threads, we must
        # ensure thread synchronization here. Further more, because we use greenthread in
        # master service, we also should use green lock.
        with self.lock:
            self.worker_api.pre_deduct(context.get_admin_context(),
                                       order_id)

    def _utc_to_local(self, utc_dt):
        from_zone = tz.tzutc()
        to_zone = tz.tzlocal()
        return utc_dt.replace(tzinfo=from_zone).astimezone(to_zone).replace(tzinfo=None)

    def _create_cron_job(self, order_id, action_time=None, start_date=None):
        """For now, we only support hourly cron job
        """
        if action_time:
            action_time = timeutils.parse_strtime(action_time,
                                                  fmt=TIMESTAMP_TIME_FORMAT)
            start_date = action_time + timedelta(hours=1)

        start_date = self._utc_to_local(start_date)

        job = self.apsched.add_interval_job(self._pre_deduct,
                                            hours=1,
                                            start_date=start_date,
                                            name=order_id,
                                            #seconds=300,
                                            #start_date=action_time + timedelta(seconds=300),
                                            args=[order_id])
        self.jobs[order_id] = job

    def _delete_cron_job(self, order_id):
        """Delete cron job related to this subscription
        """
        # FIXME(suo): Actually, we should store job to DB layer, not
        # in memory
        job = self.jobs.get(order_id)
        self.apsched.unschedule_job(job)
        del self.jobs[order_id]

    def _change_order(self, order_id, change_to):
        # Get newest order
        order = self.db_conn.get_order(context.get_admin_context(),
                                       order_id)

        # Get new unit price and update subscriptions
        subscriptions = self.db_conn.get_subscriptions_by_order_id(
            context.get_admin_context(),
            order.order_id,
            type=change_to,
            status='inactive')

        unit_price = 0
        unit = None

        for sub in subscriptions:
            sub.status = 'active'
            sub.updated_at = datetime.datetime.utcnow()
            try:
                self.db_conn.update_subscription(context.get_admin_context(), sub)
            except Exception:
                LOG.error('Fail to update the subscription: %s' % sub.as_dict())
                raise exception.DBError(reason='Fail to update the subscription')

            unit_price += sub.unit_price * sub.quantity
            unit = sub.unit

        # Update the order
        order.unit_price = unit_price
        order.unit = unit
        order.updated_at = datetime.datetime.utcnow()
        try:
            self.db_conn.update_order(context.get_admin_context(), order)
        except Exception:
            LOG.warning('Fail to update the order: %s' % order.order_id)
            raise exception.DBError(reason='Fail to update the order')

    def resource_created(self, ctxt, order_id, action_time, remarks):
        LOG.debug('Resource created, its order_id: %s, action_time: %s' %
                  (order_id, action_time))
        with self.lock:
            self.worker_api.create_bill(context.get_admin_context(), order_id,
                                        action_time, remarks)
            self._create_cron_job(order_id, action_time=action_time)

    def resource_deleted(self, ctxt, order_id, action_time):
        LOG.debug('Resource deleted, its order_id: %s, action_time: %s' %
                  (order_id, action_time))
        with self.lock:
            self.worker_api.close_bill(context.get_admin_context(),
                                       order_id, action_time)
            self._delete_cron_job(order_id)

    def resource_changed(self, ctxt, order_id, action_time, change_to, remarks):
        LOG.debug('Resource changed, its order_id: %s, action_time: %s, will change to: %s'
                  % (order_id, action_time, change_to))
        with self.lock:
            # close the old bill
            self.worker_api.close_bill(context.get_admin_context(),
                                       order_id, action_time)
            self._delete_cron_job(order_id)

            # change the order's unit price and its active subscriptions
            self._change_order(order_id, change_to)

            # create a new bill for the updated order
            self.worker_api.create_bill(context.get_admin_context(),
                                        order_id,  action_time, remarks)
            self._create_cron_job(order_id, action_time=action_time)


def master():
    prepare_service()
    os_service.launch(MasterService()).wait()
