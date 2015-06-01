import time
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
from gringotts import services

from gringotts.services import alert

from gringotts.openstack.common import log
from gringotts.openstack.common.rpc import service as rpc_service
from gringotts.openstack.common import service as os_service
from gringotts.openstack.common import timeutils
from gringotts.openstack.common import importutils
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
    cfg.IntOpt('clean_date_jobs_interval',
               default=30,
               help="The interval to clean date jobs, unit is minute"),
]

OPTS_GLOBAL = [
    cfg.ListOpt('ignore_tenants',
                default=[],
                help="A list of tenant that should not to check and deduct"),
    cfg.BoolOpt('enable_owe',
                default=False,
                help='Enable owe logic or not'),
    cfg.BoolOpt('try_to_fix',
                default=False,
                help='Try to auto-fix or not'),
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
        self.date_jobs_after_30_days = {}
        self.lock = Lock()
        self.ctxt = context.get_admin_context()

        self.DELETE_METHOD_MAP = services.DELETE_METHOD_MAP
        self.STOP_METHOD_MAP = services.STOP_METHOD_MAP
        self.RESOURCE_GET_MAP = services.RESOURCE_GET_MAP

        super(MasterService, self).__init__(*args, **kwargs)

    def start(self):
        self.apsched.start()
        self.load_cron_jobs()
        LOG.warning('Load cron jobs successfully.')

        if cfg.CONF.enable_owe:
            self.load_date_jobs()
            self.load_clean_date_jobs()

        self.load_30_days_date_jobs()

        super(MasterService, self).start()
        LOG.warning('Master started successfully.')

        # Add a dummy thread to have wait() working
        self.tg.add_timer(604800, lambda: None)

    def load_clean_date_jobs(self):
        self.clean_date_jobs()
        self.apsched.add_interval_job(self.clean_date_jobs,
                                      minutes=cfg.CONF.master.clean_date_jobs_interval)
        LOG.warn('Load clean date jobs successfully')

    def load_date_jobs(self):
        states = [const.STATE_RUNNING, const.STATE_STOPPED, const.STATE_SUSPEND]
        for s in states:
            LOG.debug('Loading date jobs in %s state' % s)

            orders = self.worker_api.get_orders(self.ctxt, status=s, owed=True,
                                                region_id=cfg.CONF.region_name)

            for order in orders:
                # load delete resource date job
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

    def load_30_days_date_jobs(self):
        # load change unit price date job
        orders = self.worker_api.get_orders(self.ctxt, status=const.STATE_STOPPED,
                                            region_id=cfg.CONF.region_name,
                                            type=const.RESOURCE_INSTANCE)
        for order in orders:
            if not order['cron_time']:
                LOG.warn('There is no cron_time for the stopped order: %s' % order)
                continue
            if isinstance(order['cron_time'], basestring):
                cron_time = timeutils.parse_strtime(order['cron_time'],
                                                    fmt=ISO8601_UTC_TIME_FORMAT)
            else:
                cron_time = order['cron_time']

            danger_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=30)
            cron_time = cron_time - datetime.timedelta(hours=1)
            if cron_time > danger_time:
                self._create_date_job_after_30_days(order['order_id'], cron_time)
            else:
                LOG.warning('The order(%s) is in danger time after master started'
                            % order['order_id'])
                self._change_order_unit_price(order['order_id'])
        LOG.warning('Load 30-days date jobs successfully.')

    def load_cron_jobs(self):
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

                # create cron job
                danger_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=30)
                if cron_time > danger_time:
                    self._create_cron_job(order['order_id'],
                                          start_date=cron_time)
                else:
                    LOG.warning('The order(%s) is in danger time after master started'
                                % order['order_id'])
                    while cron_time <= danger_time:
                        cron_time += datetime.timedelta(hours=1)
                    cron_time -= datetime.timedelta(hours=1)
                    action_time = utils.format_datetime(timeutils.strtime(cron_time))
                    self._create_bill(self.ctxt,
                                      order['order_id'],
                                      action_time,
                                      "Hourly Billing")

    def _stop_owed_resource(self, resource_type, resource_id, region_id):
        LOG.warn('stop owed resource(resource_type: %s, resource_id: %s)' % \
                (resource_type, resource_id))
        method = self.STOP_METHOD_MAP[resource_type]
        try:
            method(resource_id, region_id)
        except Exception:
            time.sleep(30)
            try:
                method(resource_id, region_id)
            except Exception:
                LOG.warn('Fail to stop owed resource(resource_type: %s, resource_id: %s)' % \
                        (resource_type, resource_id))


    def _delete_owed_resource(self, resource_type, resource_id, region_id):
        # delete date job from self.date_jobs
        LOG.warn('delete date job for resource: %s' % resource_id)
        job = self.date_jobs.get(resource_id)
        if not job:
            LOG.warning('There is no date job for the resource: %s' % resource_id)
        else:
            del self.date_jobs[resource_id]

        # delete the resource first
        LOG.warn('delete owed resource(resource_type: %s, resource_id: %s)' % \
                (resource_type, resource_id))
        method = self.DELETE_METHOD_MAP[resource_type]
        try:
            method(resource_id, region_id)
        except Exception:
            time.sleep(30)
            try:
                method(resource_id, region_id)
            except Exception:
                LOG.warn('Fail to delete owed resource(resource_type: %s, resource_id: %s)' % \
                        (resource_type, resource_id))

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

        LOG.warn('create cron job for order: %s' % order_id)

    def _delete_cron_job(self, order_id):
        """Delete cron job related to this subscription
        """
        job = self.cron_jobs.get(order_id)
        if not job:
            LOG.warning('There is no cron job for the order: %s' % order_id)
            return
        try:
            self.apsched.unschedule_job(job)
        except KeyError:
            LOG.warn('Fail to unschedule cron job: %s' % job)
        try:
            del self.cron_jobs[order_id]
        except KeyError:
            LOG.warn('Fail to delete cron job of resource: %s' % resource_id)

        LOG.warn('delete cron job for order: %s' % order_id)

    def _create_date_job(self, resource_type, resource_id, region_id,
                         action_time):
        if isinstance(action_time, basestring):
            action_time = timeutils.parse_strtime(action_time,
                                                  fmt=ISO8601_UTC_TIME_FORMAT)
        action_time = utils.utc_to_local(action_time)
        job = self.apsched.add_date_job(self._delete_owed_resource,
                                        action_time,
                                        name=resource_id,
                                        args=[resource_type,
                                              resource_id,
                                              region_id])
        self.date_jobs[resource_id] = job

        LOG.warn('create date job for resource: %s' % resource_id)

    def _change_order_unit_price(self, order_id):
        self.worker_api.change_order(self.ctxt, order_id, const.STATE_STOPPED)

    def _create_date_job_after_30_days(self, order_id, action_time):
        action_time = utils.utc_to_local(action_time)
        job = self.apsched.add_date_job(self._change_order_unit_price,
                                        action_time,
                                        name=order_id,
                                        args=[order_id])
        self.date_jobs_after_30_days[order_id] = job

        LOG.warn('create 30-days date job for order: %s' % order_id)

    def _delete_date_job_after_30_days(self, order_id):
        job = self.date_jobs_after_30_days.get(order_id)
        if not job:
            LOG.warning('There is no 30 days date job for order: %s' % order_id)
            return
        try:
            self.apsched.unschedule_job(job)
        except KeyError:
            LOG.warn('Fail to unschedule 30 days date job: %s' % job)
        try:
            del self.date_jobs_after_30_days[order_id]
        except  KeyError:
            LOG.warn('Fail to delete 30 days date job of order: %s' % order_id)

        LOG.warn('delete 30-days date job for order: %s' % order_id)

    def _delete_date_job(self, resource_id):
        """Delete date job related to this order
        """
        job = self.date_jobs.get(resource_id)
        if not job:
            LOG.warning('There is no date job for the resource: %s' % resource_id)
            return
        try:
            self.apsched.unschedule_job(job)
        except KeyError:
            LOG.warn('Fail to unschedule date job: %s' % job)
        try:
            del self.date_jobs[resource_id]
        except  KeyError:
            LOG.warn('Fail to delete date job of resource: %s' % resource_id)

        LOG.warn('delete date job for resource: %s' % resource_id)

    def _pre_deduct(self, order_id):
        try:
            # check resource and order before deduct
            order = self.worker_api.get_order(self.ctxt, order_id)

            # do not deduct doctor project for now
            if order['project_id'] in cfg.CONF.ignore_tenants:
                return

            method = self.RESOURCE_GET_MAP[order['type']]
            resource = method(order['resource_id'], order['region_id'])
            if not resource:
                # alert that the resource not exists
                LOG.warn("The resource(%s|%s) has been deleted" % \
                         (order['type'], order['resource_id']))
                alert.wrong_billing_order(order, 'resource_deleted')

                # try to fix
                if cfg.CONF.try_to_fix:
                    deleted_at = utils.format_datetime(timeutils.strtime())
                    self.resource_deleted(self.ctxt, order['order_id'],
                                          deleted_at,
                                          "Resource Has Been Deleted")
                return

            # TODO(suo): Too ugly, maybe should have another order_status attribute in resource,
            # status is just for judging resource status, and order_status is for determining
            # order status
            if (resource.resource_type == const.RESOURCE_LISTENER and resource.admin_state != order['status']) or \
                    (resource.resource_type != const.RESOURCE_LISTENER and resource.status != order['status']):
                # alert that the status of resource and order don't match
                LOG.warn("The status of the resource(%s|%s|%s) doesn't match with the order(%s|%s|%s)." % \
                          (resource.resource_type, resource.id, resource.original_status,
                           order['type'], order['order_id'], order['status']))
                alert.wrong_billing_order(order, 'miss_match', resource)

                # try to fix
                if cfg.CONF.try_to_fix:
                    action_time = utils.format_datetime(timeutils.strtime())
                    change_to = resource.admin_state if hasattr(resource, 'admin_state') \
                            else resource.status
                    self.resource_changed(self.ctxt, order['order_id'], action_time,
                                          change_to, "System Adjust")
                return

            if isinstance(order['cron_time'], basestring):
                cron_time = timeutils.parse_strtime(order['cron_time'],
                                                    fmt=ISO8601_UTC_TIME_FORMAT)
            else:
                cron_time = order['cron_time']

            remarks = 'Hourly Billing'
            now = timeutils.utcnow()
            if now - cron_time >= timedelta(hours=1):
                result = self.worker_api.create_bill(self.ctxt,
                                                     order_id,
                                                     action_time=now,
                                                     remarks=remarks)
            else:
                result = self.worker_api.create_bill(self.ctxt, order_id, remarks=remarks)

            # Order is owed
            if result['type'] == 2:
                self._stop_owed_resource(result['resource_type'],
                                         result['resource_id'],
                                         result['region_id'])
                self._create_date_job(result['resource_type'],
                                      result['resource_id'],
                                      result['region_id'],
                                      result['date_time'])
            # Account is charged but order is still owed
            elif result['type'] == 3:
                self._delete_date_job(result['resource_id'])
        except Exception as e:
            LOG.warn("Some exceptions happen when deducting order: %s, for reason: %s" \
                     % (order_id, e))

    def _create_bill(self, ctxt, order_id, action_time, remarks):
        # create a bill
        result = self.worker_api.create_bill(ctxt, order_id, action_time, remarks)

        # Account is charged but order is still owed
        if result['type'] == 3:
            self._delete_date_job(result['resource_id'])

        self._create_cron_job(order_id, action_time=action_time)

    def _close_bill(self, ctxt, order_id, action_time):
        result = self.worker_api.close_bill(ctxt, order_id, action_time)
        self._delete_cron_job(order_id)
        return result

    def get_cronjob_count(self, ctxt):
        return len(self.cron_jobs)

    def get_datejob_count(self, ctxt):
        return len(self.date_jobs)

    def get_datejob_count_30_days(self, ctxt):
        return len(self.date_jobs_after_30_days)

    def resource_created(self, ctxt, order_id, action_time, remarks):
        LOG.debug('Resource created, its order_id: %s, action_time: %s',
                  order_id, action_time)
        self._create_bill(ctxt, order_id, action_time, remarks)

    def resource_created_again(self, ctxt, order_id, action_time, remarks):
        LOG.debug('Resource created again, its order_id: %s, action_time: %s',
                  order_id, action_time)
        self._create_bill(ctxt, order_id, action_time, remarks)

    def resource_deleted(self, ctxt, order_id, action_time, remarks):
        LOG.debug('Resource deleted, its order_id: %s, action_time: %s' %
                  (order_id, action_time))

        result = self._close_bill(ctxt, order_id, action_time)
        # Delete date job of owed resource
        if result['resource_owed']:
            self._delete_date_job(result['resource_id'])
        self.worker_api.change_order(ctxt, order_id, const.STATE_DELETED)

        # create a bill that tell people the resource has been deleted
        self.worker_api.create_bill(ctxt, order_id,
                                    action_time=action_time,
                                    remarks=remarks,
                                    end_time=action_time)

        # delete the date job if the order has a 30-days date job
        if self.date_jobs_after_30_days.get(order_id):
            self._delete_date_job_after_30_days(order_id)

    def resource_stopped(self, ctxt, order_id, action_time, remarks):
        LOG.debug('Resource deleted, its order_id: %s, action_time: %s' %
                  (order_id, action_time))

        result = self._close_bill(ctxt, order_id, action_time)
        # Delete date job of owed resource
        if result['resource_owed']:
            self._delete_date_job(result['resource_id'])
        self.worker_api.change_order(ctxt, order_id, const.STATE_STOPPED)

        # create a bill that tell people the resource has been stopped
        self.worker_api.create_bill(ctxt, order_id,
                                    action_time=action_time,
                                    remarks=remarks,
                                    end_time=action_time)

    def resource_started(self, ctxt, order_id, action_time, remarks):
        LOG.debug('Resource created, its order_id: %s, action_time: %s',
                  order_id, action_time)
        result = self.worker_api.close_bill(ctxt, order_id, action_time)
        self.worker_api.change_order(ctxt, order_id, const.STATE_RUNNING)
        self._create_bill(ctxt, order_id, action_time, remarks)

    def resource_changed(self, ctxt, order_id, action_time, change_to, remarks):
        LOG.debug('Resource changed, its order_id: %s, action_time: %s, will change to: %s'
                  % (order_id, action_time, change_to))
        # close the old bill
        self._close_bill(ctxt, order_id, action_time)

        # change the order's unit price and its active subscriptions
        self.worker_api.change_order(ctxt, order_id, change_to)

        # create a new bill for the updated order
        self._create_bill(ctxt, order_id, action_time, remarks)

        # delete the date job if the order has a 30-days date job
        if self.date_jobs_after_30_days.get(order_id):
            self._delete_date_job_after_30_days(order_id)

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
                                     const.STATE_STOPPED_IN_30_DAYS,
                                     cron_time=cron_time,
                                     first_change_to=const.STATE_STOPPED)

        # create a bill cross 30 days
        self.worker_api.create_bill(ctxt, order_id,
                                    action_time=action_time,
                                    remarks="Instance Has Been Stopped",
                                    end_time=cron_time)

        # create a date job to change order unit price after 30 days
        # let this action execute 1 hour earlier to ensure unit price be changed
        # before pre deduct
        self._create_date_job_after_30_days(order_id,
                                            cron_time-datetime.timedelta(hours=1))

        # create a cron job that will execute after 30 days
        self._create_cron_job(order_id, start_date=cron_time)

    def instance_resized(self, ctxt, order_id, action_time,
                         new_flavor, old_flavor,
                         service, region_id, remarks):
        """Instance resized, update the flavor subscription, and change order

        NOTE(suo): This method will not use right now, because only stopped
                   instance can executes resize command, and stopped instance
                   is not charged for a month. So, just change subscription and
                   order in waiter is enough, should not close/create bill for the
                   resource in master
        """
        LOG.debug("Instance resized, its order_id: %s, action_time: %s"
                  % (order_id, action_time))

        # close the old bill
        self._close_bill(ctxt, order_id, action_time)

        # change subscirption's quantity
        self.worker_api.change_flavor_subscription(self.ctxt, order_id,
                                                   new_flavor, old_flavor,
                                                   service, region_id,
                                                   const.STATE_RUNNING)

        # change the order's unit price and its active subscriptions
        self.worker_api.change_order(self.ctxt, order_id, const.STATE_RUNNING)

        # create a new bill for the updated order
        self._create_bill(ctxt, order_id, action_time, remarks)

    def clean_date_jobs(self):
        LOG.warn('Doing clean date jobs')
        orders = self.worker_api.get_active_orders(self.ctxt, charged=True,
                                                   region_id=cfg.CONF.region_name)

        order_ids = []
        for order in orders:
            order_ids.append(order['order_id'])
            self._delete_date_job(order['resource_id'])

        if order_ids:
            self.worker_api.reset_charged_orders(self.ctxt, order_ids)


def master():
    prepare_service()
    os_service.launch(MasterService()).wait()
