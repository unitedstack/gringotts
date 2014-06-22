import datetime

from datetime import timedelta

from oslo.config import cfg
from eventlet.green.threading import Lock

from apscheduler.scheduler import Scheduler as APScheduler

from gringotts import constants as const
from gringotts import context
from gringotts import worker
from gringotts import exception
from gringotts import utils

from gringotts.openstack.common import log
from gringotts.openstack.common.rpc import service as rpc_service
from gringotts.openstack.common import service as os_service
from gringotts.openstack.common import timeutils
from gringotts.service import prepare_service


LOG = log.getLogger(__name__)

TIMESTAMP_TIME_FORMAT = '%Y-%m-%d %H:%M:%S.%f'
ISO8601_UTC_TIME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'

OPTS = [
    cfg.IntOpt('apscheduler_threadpool_max_threads',
               default=10,
               help='Maximum number of total threads in the pool'),
    cfg.IntOpt('apscheduler_threadpool_core_threads',
               default=10,
               help='Maximum number of persistent threads in the pool'),
    cfg.StrOpt('master_topic',
               default='gringotts.master',
               help='the topic master listen on'),
    cfg.IntOpt('allow_delay_seconds',
               default=300,
               help="The delay seconds that allows between nodes"),
]

OPTS_GLOBAL = [
    cfg.BoolOpt('enable_owe',
                default=False,
                help='Enable owe logic or not')
]

cfg.CONF.register_opts(OPTS_GLOBAL)
cfg.CONF.register_opts(OPTS, group="master")
cfg.CONF.import_opt('region_name', 'gringotts.waiter.service')


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

        from gringotts.services import cinder
        from gringotts.services import glance
        from gringotts.services import neutron
        from gringotts.services import nova

        self.DELETE_METHOD_MAP = {
            const.RESOURCE_INSTANCE: nova.delete_server,
            const.RESOURCE_IMAGE: glance.delete_image,
            const.RESOURCE_SNAPSHOT: cinder.delete_snapshot,
            const.RESOURCE_VOLUME: cinder.delete_volume,
            const.RESOURCE_FLOATINGIP: neutron.delete_fip,
            const.RESOURCE_ROUTER: neutron.delete_router,
        }

        self.STOP_METHOD_MAP = {
            const.RESOURCE_INSTANCE: nova.stop_server,
            const.RESOURCE_IMAGE: glance.stop_image,
            const.RESOURCE_SNAPSHOT: cinder.stop_snapshot,
            const.RESOURCE_VOLUME: cinder.stop_volume,
            const.RESOURCE_FLOATINGIP: neutron.stop_fip,
            const.RESOURCE_ROUTER: neutron.stop_router,
        }

        super(MasterService, self).__init__(*args, **kwargs)

    def start(self):
        self.apsched.start()
        self.load_jobs()
        LOG.warning('Jobs loaded successfully.')

        super(MasterService, self).start()
        LOG.warning('Master started successfully.')

        if cfg.CONF.enable_owe:
            self.load_date_jobs()

        # Add a dummy thread to have wait() working
        self.tg.add_timer(604800, lambda: None)

    def load_date_jobs(self):
        action_time = datetime.datetime.utcnow() + timedelta(minutes=1)
        action_time = utils.utc_to_local(action_time)
        self.apsched.add_date_job(self._load_date_jobs,
                                  action_time)

    def _load_date_jobs(self):
        states = [const.STATE_RUNNING, const.STATE_STOPPED, const.STATE_SUSPEND]
        for s in states:
            LOG.debug('Loading date jobs in %s state' % s)

            orders = self.worker_api.get_orders(self.ctxt, status=s, owed=True,
                                                region_id=cfg.CONF.region_name)

            for order in orders:
                if isinstance(order['date_time'], basestring):
                    date_time = timeutils.parse_strtime(order['date_time'],
                                                        fmt=ISO8601_UTC_TIME_FORMAT)
                else:
                    date_time = order['date_time']

                danger_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=30)
                if date_time > danger_time:
                    self._create_date_job(order['type'],
                                          order['resource_id'],
                                          order['region_id'],
                                          order['date_time'])
                else:
                    LOG.warning('The resource(%s) is in danger time after master started'
                                % order['resource_id'])
                    self._delete_owed_resource(order['type'],
                                               order['resource_id'],
                                               order['region_id'])
        LOG.warning('Load date jobs successfully.')

    def load_jobs(self):
        states = [const.STATE_RUNNING, const.STATE_STOPPED, const.STATE_SUSPEND]
        for s in states:
            LOG.debug('Loading jobs in %s state' % s)

            orders = self.worker_api.get_orders(self.ctxt, status=s,
                                                region_id=cfg.CONF.region_name)

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

    def _stop_owed_resource(self, resource_type, resource_id, region_id):
        method = self.STOP_METHOD_MAP[resource_type]
        return method(resource_id, region_id)

    def _delete_owed_resource(self, resource_type, resource_id, region_id):
        try:
            del self.date_jobs[resource_id]
        except IndexError:
            pass
        method = self.DELETE_METHOD_MAP[resource_type]
        method(resource_id, region_id)

    def _create_cron_job(self, order_id, action_time=None, start_date=None):
        """For now, we only support hourly cron job
        """
        if action_time:
            action_time = timeutils.parse_strtime(action_time,
                                                  fmt=TIMESTAMP_TIME_FORMAT)
            start_date = action_time + timedelta(hours=1)

        start_date = utils.utc_to_local(start_date)

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
        if not job:
            LOG.warning('There is no cron job for the order: %s' % order_id)
            return
        self.apsched.unschedule_job(job)
        del self.cron_jobs[order_id]

    def _create_date_job(self, resource_type, resource_id, region_id,
                         action_time):
        if isinstance(action_time, basestring):
            action_time = timeutils.parse_strtime(action_time,
                                                  fmt=ISO8601_UTC_TIME_FORMAT)
        action_time = utils.utc_to_local(action_time)
        job = self.apsched.add_date_job(self._delete_owed_resource,
                                        action_time,
                                        args=[resource_type,
                                              resource_id,
                                              region_id])
        self.date_jobs[resource_id] = job

    def _delete_date_job(self, resource_id):
        """Delete date job related to this order
        """
        job = self.date_jobs.get(resource_id)
        if not job:
            LOG.warning('There is no date job for the resource: %s' % resource_id)
            return
        self.apsched.unschedule_job(job)
        del self.date_jobs[resource_id]

    def _pre_deduct(self, order_id):
        remarks = 'Hourly Billing'
        result = self.worker_api.create_bill(self.ctxt, order_id, remarks=remarks)

        # Order is owed
        if result['type'] == 2:
            reserv = self._stop_owed_resource(result['resource_type'],
                                              result['resource_id'],
                                              result['region_id'])
            if reserv:
                self._create_date_job(result['resource_type'],
                                      result['resource_id'],
                                      result['region_id'],
                                      result['date_time'])
        # Account is charged but order is still owed
        elif result['type'] == 3:
            self._delete_date_job(result['resource_id'])

    def _create_bill(self, ctxt, order_id, action_time, remarks):
        result = self.worker_api.create_bill(ctxt, order_id, action_time, remarks)
        self._create_cron_job(order_id, action_time=action_time)

    def _close_bill(self, ctxt, order_id, action_time):
        result = self.worker_api.close_bill(ctxt, order_id, action_time)
        self._delete_cron_job(order_id)
        return result

    def get_cronjob_count(self, ctxt):
        return len(self.cron_jobs)

    def get_datejob_count(self, ctxt):
        return len(self.date_jobs)

    def resource_created(self, ctxt, order_id, action_time, remarks):
        LOG.debug('Resource created, its order_id: %s, action_time: %s',
                  order_id, action_time)
        self._create_bill(ctxt, order_id, action_time, remarks)

    def resource_created_again(self, ctxt, order_id, action_time, remarks):
        LOG.debug('Resource created again, its order_id: %s, action_time: %s',
                  order_id, action_time)
        # Create the first bill, including remarks and action_time
        result = self.worker_api.create_bill(ctxt, order_id, action_time, remarks)

        # Pre deduct...
        danger_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=30)
        action_time = timeutils.parse_strtime(action_time,
                                              fmt=TIMESTAMP_TIME_FORMAT)
        cron_time = action_time + datetime.timedelta(hours=1)

        if cron_time > danger_time:
            self._create_cron_job(order_id,
                                  start_date=cron_time)
        else:
            while cron_time <= danger_time:
                self._pre_deduct(order_id)
                cron_time += datetime.timedelta(hours=1)
            self._create_cron_job(order_id, start_date=cron_time)

    def resource_deleted(self, ctxt, order_id, action_time):
        LOG.debug('Resource deleted, its order_id: %s, action_time: %s' %
                  (order_id, action_time))
        result = self._close_bill(ctxt, order_id, action_time)
        # Delete date job of owed resource
        if result['resource_owed']:
            self._delete_date_job(result['resource_id'])
        self.worker_api.change_order(ctxt, order_id, const.STATE_DELETED)

    def resource_changed(self, ctxt, order_id, action_time, change_to, remarks):
        LOG.debug('Resource changed, its order_id: %s, action_time: %s, will change to: %s'
                  % (order_id, action_time, change_to))
        # close the old bill
        self._close_bill(ctxt, order_id, action_time)

        # change the order's unit price and its active subscriptions
        self.worker_api.change_order(ctxt, order_id, change_to)

        # create a new bill for the updated order
        self._create_bill(ctxt, order_id, action_time, remarks)

    def resource_resized(self, ctxt, order_id, action_time, quantity, remarks):
        LOG.debug('Resource resized, its order_id: %s, action_time: %s, will resize to: %s'
                  % (order_id, action_time, quantity))
        # close the old bill
        self._close_bill(ctxt, order_id, action_time)

        # change subscirption's quantity
        self.worker_api.change_subscription(self.ctxt, order_id,
                                            quantity, const.STATE_RUNNING)

        # change the order's unit price and its active subscriptions
        self.worker_api.change_order(self.ctxt, order_id, const.STATE_RUNNING)

        # create a new bill for the updated order
        self._create_bill(ctxt, order_id, action_time, remarks)

    def instance_stopped(self, ctxt, order_id, action_time):
        """Instance stopped for a month continuously will not be charged
        """
        LOG.debug("Instance stopped, its order_id: %s, action_time: %s"
                  % (order_id, action_time))

        # close the old bill
        self._close_bill(ctxt, order_id, action_time)

        # Caculate cron_time after 30 days from now
        action_time = timeutils.parse_strtime(action_time,
                                              fmt=TIMESTAMP_TIME_FORMAT)
        cron_time = action_time + datetime.timedelta(days=30)

        # change the order's unit price and its active subscriptions
        self.worker_api.change_order(ctxt, order_id,
                                     const.STATE_STOPPED,
                                     cron_time=cron_time)

        # create a cron job that will execute after one month
        self._create_cron_job(order_id, start_date=cron_time)


def master():
    prepare_service()
    os_service.launch(MasterService()).wait()
