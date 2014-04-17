import datetime

from datetime import timedelta
from dateutil import tz

from oslo.config import cfg
from eventlet.green.threading import Lock

from apscheduler.scheduler import Scheduler as APScheduler

from gringotts import constants as const
from gringotts import context
from gringotts import worker

from gringotts.openstack.common import log
from gringotts.openstack.common.rpc import service as rpc_service
from gringotts.openstack.common import service as os_service
from gringotts.openstack.common import timeutils
from gringotts.service import prepare_service


LOG = log.getLogger(__name__)

TIMESTAMP_TIME_FORMAT = '%Y-%m-%d %H:%M:%S.%f'
ISO8601_UTC_TIME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'

OPTS = [
    cfg.IntOpt('reserved_days',
               default=7,
               help='Reserved days after the resource is owed'),
    cfg.IntOpt('apscheduler_threadpool_max_threads',
               default=10,
               help='Maximum number of total threads in the pool'),
    cfg.IntOpt('apscheduler_threadpool_core_threads',
               default=10,
               help='Maximum number of persistent threads in the pool'),
    cfg.StrOpt('master_topic',
               default='gringotts.master',
               help='the topic master listen on'),
]

cfg.CONF.register_opts(OPTS, group="master")


class MasterService(rpc_service.Service):

    def __init__(self, *args, **kwargs):
        kwargs.update(
            host=cfg.CONF.host,
            topic=cfg.CONF.master.master_topic,
        )
        self.worker_api = worker.API()

        config = {
            'apscheduler.misfire_grace_time': 604800,
            'apscheduler.coalesce': False,
            'apscheduler.threadpool.max_threads': cfg.CONF.master.apscheduler_threadpool_max_threads,
            'apscheduler.threadpool.core_threads': cfg.CONF.master.apscheduler_threadpool_core_threads,
            'apscheduler.threadpool.keepalive': 1,
        }
        self.apsched = APScheduler(config)

        self.cron_jobs = {}
        self.date_jobs = {}
        self.lock = Lock()
        self.ctxt = context.get_admin_context()
        super(MasterService, self).__init__(*args, **kwargs)

    def start(self):
        self.apsched.start()
        self.load_jobs()
        LOG.warning('Jobs loaded successfully.')

        super(MasterService, self).start()
        LOG.warning('Master started successfully.')

        # Add a dummy thread to have wait() working
        self.tg.add_timer(604800, lambda: None)

    def load_jobs(self):
        states = [const.STATE_RUNNING, const.STATE_STOPPED, const.STATE_SUSPEND]
        for s in states:
            LOG.debug('Loading jobs in %s state' % s)

            orders = self.worker_api.get_orders(self.ctxt, status=s)

            for order in orders:
                if not order['cron_time']:
                    continue
                elif isinstance(order['cron_time'], basestring):
                    cron_time = timeutils.parse_strtime(order['cron_time'],
                                                        fmt=ISO8601_UTC_TIME_FORMAT)
                else:
                    cron_time = order['cron_time']

                danger_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=30)
                if cron_time > danger_time:
                    self._create_cron_job(order['order_id'],
                                          start_date=cron_time)
                else:
                    LOG.warning('The order(%s) is in danger time after master started'
                                % order['order_id'])
                    while cron_time <= danger_time:
                        self._pre_deduct(order['order_id'])
                        cron_time += datetime.timedelta(hours=1)
                    self._create_cron_job(order['order_id'],
                                          start_date=cron_time)

    def _pre_deduct(self, order_id):
        remarks = 'Hourly Billing'
        self.worker_api.create_bill(self.ctxt, order_id, remarks=remarks)

    def _destroy_resource(self, order_id):
        """Destroy the resource

        1. The resource will be destroyed after reserved days
        2. The order's owed cron job must be removed
        3. Change the order status to deleted
        """
        self.worker_api.destory_resource(self.ctxt, order_id)
        self._delete_cron_job(order_id)
        self._change_order(order_id, const.STATE_DELETED)

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
                                            args=[order_id],
                                            max_instances=604800)
        self.cron_jobs[order_id] = job

    def _delete_cron_job(self, order_id):
        """Delete cron job related to this subscription
        """
        job = self.cron_jobs.get(order_id)
        self.apsched.unschedule_job(job)
        del self.cron_jobs[order_id]

    def _create_date_job(self, order_id, action_time):
        action_time = self._utc_to_local(action_time)
        job = self.apsched.add_date_job(self._destroy_resource,
                                        action_time,
                                        args=[order_id])
        self.date_jobs[order_id] = job

    def _delete_date_job(self, order_id):
        """Delete date job related to this order
        """
        job = self.date_jobs.get(order_id)
        self.apsched.unschedule_job(job)
        del self.date_jobs[order_id]

    def resource_created(self, ctxt, order_id, action_time, remarks):
        LOG.debug('Resource created, its order_id: %s, action_time: %s',
                  order_id, action_time)
        self.worker_api.create_bill(self.ctxt, order_id, action_time, remarks)
        self._create_cron_job(order_id, action_time=action_time)

    def resource_deleted(self, ctxt, order_id, action_time):
        LOG.debug('Resource deleted, its order_id: %s, action_time: %s' %
                  (order_id, action_time))
        self.worker_api.close_bill(self.ctxt, order_id, action_time)
        self._delete_cron_job(order_id)
        self.worker_api.change_order(self.ctxt, order_id, const.STATE_DELETED)

    def resource_changed(self, ctxt, order_id, action_time, change_to, remarks):
        LOG.debug('Resource changed, its order_id: %s, action_time: %s, will change to: %s'
                  % (order_id, action_time, change_to))
        # close the old bill
        self.worker_api.close_bill(self.ctxt, order_id, action_time)
        self._delete_cron_job(order_id)

        # change the order's unit price and its active subscriptions
        self.worker_api.change_order(self.ctxt, order_id, change_to)

        # create a new bill for the updated order
        self.worker_api.create_bill(self.ctxt, order_id, action_time, remarks)
        self._create_cron_job(order_id, action_time=action_time)

    def resource_resized(self, ctxt, order_id, action_time, quantity, remarks):
        LOG.debug('Resource resized, its order_id: %s, action_time: %s, will resize to: %s'
                  % (order_id, action_time, quantity))
        # close the old bill
        self.worker_api.close_bill(self.ctxt, order_id, action_time)
        self._delete_cron_job(order_id)

        # change subscirption's quantity
        self.worker_api.change_subscription(self.ctxt, order_id,
                                            quantity, const.STATE_RUNNING)

        # change the order's unit price and its active subscriptions
        self.worker_api.change_order(self.ctxt, order_id, const.STATE_RUNNING)

        # create a new bill for the updated order
        self.worker_api.create_bill(self.ctxt, order_id, action_time, remarks)
        self._create_cron_job(order_id, action_time=action_time)


def master():
    prepare_service()
    os_service.launch(MasterService()).wait()
