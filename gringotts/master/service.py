import datetime
import time

from apscheduler.schedulers import background  # noqa
from eventlet.green import threading as gthreading  # noqa
from oslo.config import cfg
import pytz

from gringotts.client import client
from gringotts import constants as const
from gringotts import context
from gringotts.openstack.common import log
from gringotts.openstack.common.rpc import service as rpc_service
from gringotts.openstack.common import service as os_service
from gringotts.openstack.common import timeutils
from gringotts import service
from gringotts import services
from gringotts import utils


LOG = log.getLogger(__name__)

TIMESTAMP_TIME_FORMAT = '%Y-%m-%d %H:%M:%S.%f'
ISO8601_UTC_TIME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'

OPTS = [
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

        self.locks = {}
        self.gclient = client.get_client()
        self.ctxt = context.get_admin_context()

        job_defaults = {
            'misfire_grace_time': 6048000,
            'coalesce': False,
            'max_instances': 24,
        }
        self.apsched = background.BackgroundScheduler(
            job_defaults=job_defaults,
            timezone=pytz.utc)

        self.DELETE_METHOD_MAP = services.DELETE_METHOD_MAP
        self.STOP_METHOD_MAP = services.STOP_METHOD_MAP
        self.RESOURCE_GET_MAP = services.RESOURCE_GET_MAP

        super(MasterService, self).__init__(*args, **kwargs)

    def start(self):
        self.apsched.start()
        self.load_hourly_cron_jobs()
        self.load_monthly_cron_jobs()
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
        self.apsched.add_job(self.clean_date_jobs,
                             'interval',
                             minutes=cfg.CONF.master.clean_date_jobs_interval)
        LOG.warn('Load clean date jobs successfully')

    def load_date_jobs(self):
        states = [const.STATE_RUNNING, const.STATE_STOPPED,
                  const.STATE_SUSPEND]
        for s in states:
            LOG.debug('Loading date jobs in %s state', s)

            orders = self.gclient.get_orders(status=s, owed=True,
                                             region_id=cfg.CONF.region_name)

            for order in orders:
                # load delete resource date job
                if isinstance(order['date_time'], basestring):
                    date_time = timeutils.parse_strtime(
                        order['date_time'], fmt=ISO8601_UTC_TIME_FORMAT)
                else:
                    date_time = order['date_time']

                danger_time = (datetime.datetime.utcnow() +
                               datetime.timedelta(seconds=30))
                if date_time > danger_time:
                    self._create_date_job(order['order_id'],
                                          order['type'],
                                          order['resource_id'],
                                          order['region_id'],
                                          order['date_time'])
                else:
                    LOG.warning('The resource(%s) is in danger time after '
                                'master started', order['resource_id'])
                    self._delete_owed_resource(order['type'],
                                               order['resource_id'],
                                               order['region_id'])

        LOG.warning('Load date jobs successfully.')

    def load_30_days_date_jobs(self):
        # load change unit price date job
        orders = self.gclient.get_orders(status=const.STATE_STOPPED,
                                         region_id=cfg.CONF.region_name,
                                         bill_methods=['hour'],
                                         type=const.RESOURCE_INSTANCE)
        for order in orders:
            if not order['cron_time']:
                LOG.warn('There is no cron_time for the stopped order: %s',
                         order)
                continue
            if isinstance(order['cron_time'], basestring):
                cron_time = timeutils.parse_strtime(
                    order['cron_time'], fmt=ISO8601_UTC_TIME_FORMAT)
            else:
                cron_time = order['cron_time']

            danger_time = (datetime.datetime.utcnow() +
                           datetime.timedelta(seconds=30))
            cron_time = cron_time - datetime.timedelta(hours=1)
            if cron_time > danger_time:
                self._create_date_job_after_30_days(order['order_id'],
                                                    cron_time)
            else:
                LOG.warning("The order(%s) is in danger time after master "
                            "started", order['order_id'])
                self._change_order_unit_price(order['order_id'])
        LOG.warning('Load 30-days date jobs successfully.')

    def _get_cron_orders(self, bill_methods=None, owed=None):
        orders = []
        states = [const.STATE_RUNNING, const.STATE_STOPPED,
                  const.STATE_SUSPEND]
        for s in states:
            orders += self.gclient.get_orders(status=s,
                                              owed=owed,
                                              bill_methods=bill_methods,
                                              region_id=cfg.CONF.region_name)
        return orders

    def load_monthly_cron_jobs(self):
        """Load monthly cron jobs

        Because owed monthly resource will not cron again, so there is no
        need to load owed monthly resources
        """
        # owed="" will be tranlated to owed=False by wsme
        orders = self._get_cron_orders(bill_methods=['month', 'year'],
                                       owed="")
        for order in orders:
            if not order['cron_time']:
                continue
            elif isinstance(order['cron_time'], basestring):
                cron_time = timeutils.parse_strtime(
                    order['cron_time'], fmt=ISO8601_UTC_TIME_FORMAT)
            else:
                cron_time = order['cron_time']

            # Because if not specify run_date for date_time job or the
            # specified run_date is less than the current time, the date
            # time job will use the current time, so there is no need to
            # distinguish the danger_time
            self._create_monthly_job(order['order_id'],
                                     run_date=cron_time)
            self.locks[order['order_id']] = gthreading.Lock()

    def load_hourly_cron_jobs(self):
        orders = self._get_cron_orders(bill_methods=['hour'])
        for order in orders:
            if not order['cron_time']:
                continue
            elif isinstance(order['cron_time'], basestring):
                cron_time = timeutils.parse_strtime(
                    order['cron_time'], fmt=ISO8601_UTC_TIME_FORMAT)
            else:
                cron_time = order['cron_time']

            # create cron job
            danger_time = (datetime.datetime.utcnow() +
                           datetime.timedelta(seconds=30))
            if cron_time > danger_time:
                self._create_cron_job(order['order_id'],
                                      start_date=cron_time)
            else:
                LOG.warning("The order(%s) is in danger time after master "
                            "started", order['order_id'])
                while cron_time <= danger_time:
                    cron_time += datetime.timedelta(hours=1)
                cron_time -= datetime.timedelta(hours=1)
                action_time = utils.format_datetime(
                    timeutils.strtime(cron_time))
                self._create_bill(self.ctxt,
                                  order['order_id'],
                                  action_time,
                                  "System Adjust")
            self.locks[order['order_id']] = gthreading.Lock()

    def _make_30_days_job_id(self, order_id):
        return "30-days-" + order_id

    def _make_cron_job_id(self, order_id):
        return "cron-" + order_id

    def _make_date_job_id(self, order_id):
        return "date-" + order_id

    def _make_monthly_job_id(self, order_id):
        return "monthly-" + order_id

    def _delete_cron_job(self, order_id):
        job_id = self._make_cron_job_id(order_id)
        self._delete_apsched_job(job_id)

    def _delete_date_job(self, order_id):
        job_id = self._make_date_job_id(order_id)
        self._delete_apsched_job(job_id)

    def _delete_30_days_job(self, order_id):
        job_id = self._make_30_days_job_id(order_id)
        self._delete_apsched_job(job_id)

    def _delete_monthly_job(self, order_id):
        job_id = self._make_monthly_job_id(order_id)
        self._delete_apsched_job(job_id)

    def _delete_apsched_job(self, job_id):
        """Delete this job from apscheduler
        """
        job = self.apsched.get_job(job_id)
        if job:
            self.apsched.remove_job(job_id)
            LOG.warn('Remove job %s successfully', job_id)
        else:
            LOG.warn('There is no job: %s', job_id)

    def _delete_owed_resource(self, resource_type, resource_id, region_id):
        LOG.warn("Delete owed resource(resource_type: %s, resource_id: %s)",
                 resource_type, resource_id)
        method = self.DELETE_METHOD_MAP[resource_type]
        try:
            method(resource_id, region_id)
        except Exception:
            time.sleep(30)
            try:
                method(resource_id, region_id)
            except Exception:
                LOG.warn("Fail to delete owed resource(resource_type: %s,"
                         "resource_id: %s)", resource_type, resource_id)

    def _create_date_job(self, order_id, resource_type, resource_id, region_id,
                         action_time):
        """Create a date job to delete the owed resource

        This job will be executed once, the job id is resource_id.
        """
        job_id = self._make_date_job_id(order_id)
        if isinstance(action_time, basestring):
            action_time = timeutils.parse_strtime(action_time,
                                                  fmt=ISO8601_UTC_TIME_FORMAT)

        self.apsched.add_job(self._delete_owed_resource,
                             'date',
                             args=[resource_type,
                                   resource_id,
                                   region_id],
                             id=job_id,
                             run_date=action_time,
                             replace_existing=True)
        LOG.warn('create date job for order: %s', order_id)

    def _change_order_unit_price(self, order_id):
        self.gclient.change_order(order_id, const.STATE_STOPPED)

    def _create_date_job_after_30_days(self, order_id, action_time):
        """Create a date job to change order unit price after 30 days

        This job will be only used to instance, thhe job id is
        30_days_+order_id.
        """
        job_id = self._make_30_days_job_id(order_id)
        self.apsched.add_job(self._change_order_unit_price,
                             'date',
                             args=[order_id],
                             id=job_id,
                             run_date=action_time)
        LOG.warn('create 30-days date job for order: %s', order_id)

    def _stop_owed_resource(self, resource_type, resource_id, region_id):
        LOG.warn("Stop owed resource(resource_type: %s, resource_id: %s)",
                 resource_type, resource_id)
        method = self.STOP_METHOD_MAP[resource_type]
        try:
            method(resource_id, region_id)
        except Exception:
            time.sleep(30)
            try:
                method(resource_id, region_id)
            except Exception:
                LOG.warn("Fail to stop owed resource(resource_type: %s, "
                         "resource_id: %s)", resource_type, resource_id)

    def _create_cron_job(self, order_id, action_time=None, start_date=None):
        """Create a interval job to deduct the order

        This kind of job will be executed periodically, the job id is order_id
        """
        job_id = self._make_cron_job_id(order_id)
        if action_time:
            action_time = timeutils.parse_strtime(action_time,
                                                  fmt=TIMESTAMP_TIME_FORMAT)
            start_date = action_time + datetime.timedelta(hours=1)

        self.apsched.add_job(self._pre_deduct,
                             'interval',
                             args=[order_id],
                             id=job_id,
                             hours=1,
                             start_date=start_date)
        LOG.warn('create cron job for order: %s', order_id)

    def _create_monthly_job(self, order_id, run_date):
        job_id = self._make_monthly_job_id(order_id)
        if isinstance(run_date, basestring):
            run_date = timeutils.parse_isotime(run_date)

        self.apsched.add_job(self._handle_monthly_order,
                             'date',
                             args=[order_id],
                             id=job_id,
                             run_date=run_date)
        LOG.warn('create monthly job for order: %s', order_id)

    def _get_lock(self, order_id):
        if order_id not in self.locks:
            self.locks[order_id] = gthreading.Lock()

        return self.locks.get(order_id)

    def _delete_lock(self, order_id):
        if order_id in self.locks:
            del self.locks[order_id]

    def _pre_deduct(self, order_id):
        LOG.warn("Prededucting order: %s", order_id)
        try:
            with self._get_lock(order_id):
                # check resource and order before deduct
                order = self.gclient.get_order(order_id)

                # do not deduct doctor project for now
                if order['project_id'] in cfg.CONF.ignore_tenants:
                    return

                method = self.RESOURCE_GET_MAP[order['type']]
                resource = method(order['resource_id'], order['region_id'])
                if not resource:
                    LOG.warn("The resource(%s|%s) has been deleted",
                             order['type'], order['resource_id'])
                    return

                if isinstance(order['cron_time'], basestring):
                    cron_time = timeutils.parse_strtime(
                        order['cron_time'], fmt=ISO8601_UTC_TIME_FORMAT)
                else:
                    cron_time = order['cron_time']

                remarks = 'Hourly Billing'
                now = timeutils.utcnow()
                if now - cron_time >= datetime.timedelta(hours=1):
                    result = self.gclient.create_bill(order_id,
                                                      action_time=now,
                                                      remarks=remarks)
                else:
                    result = self.gclient.create_bill(order_id,
                                                      remarks=remarks)

                # Order is owed
                if result['type'] == const.BILL_ORDER_OWED:
                    self._stop_owed_resource(result['resource_type'],
                                             result['resource_id'],
                                             result['region_id'])
                    self._create_date_job(order_id,
                                          result['resource_type'],
                                          result['resource_id'],
                                          result['region_id'],
                                          result['date_time'])
                # Account is charged but order is still owed
                elif result['type'] == const.BILL_OWED_ACCOUNT_CHARGED:
                    self._delete_date_job(order_id)
        except Exception as e:
            LOG.warn("Some exceptions happen when deducting order: %s, "
                     "for reason: %s", order_id, e)

    def _handle_monthly_order(self, order_id):
        LOG.warn("Handle monthly billing order: %s", order_id)
        try:
            with self._get_lock(order_id):
                # check resource and order before deduct
                order = self.gclient.get_order(order_id)

                # do not deduct doctor project for now
                if order['project_id'] in cfg.CONF.ignore_tenants:
                    return

                method = self.RESOURCE_GET_MAP[order['type']]
                resource = method(order['resource_id'], order['region_id'])
                if not resource:
                    LOG.warn("The resource(%s|%s) has been deleted",
                             order['type'], order['resource_id'])
                    return

                if order['renew_period'] > 1:
                    remarks = "Renew for %s %ss" % \
                            (order['renew_period'], order['renew_method'])
                else:
                    remarks = "Renew for %s %s" % \
                            (order['renew_period'], order['renew_method'])

                # deduct the order.
                result = self.gclient.create_bill(order_id,
                                                  remarks=remarks)

                # if deduct successfully, create another monthly job.
                if result['type'] == const.BILL_NORMAL:
                    if isinstance(order['cron_time'], basestring):
                        cron_time = timeutils.parse_strtime(
                            order['cron_time'], fmt=ISO8601_UTC_TIME_FORMAT)
                    else:
                        cron_time = order['cron_time']

                    months = utils.to_months(order['renew_method'],
                                             order['renew_period'])
                    next_cron_time = utils.add_months(cron_time, months)
                    self._create_monthly_job(order_id, next_cron_time)

                # if deduct failed because of not sufficient balance,
                # or the order's renew is not activated, stop the resource,
                # and create a date job to delete the resoruce.
                elif result['type'] == const.BILL_ORDER_OWED:
                    self._stop_owed_resource(result['resource_type'],
                                             result['resource_id'],
                                             result['region_id'])
                    self._create_date_job(order_id,
                                          result['resource_type'],
                                          result['resource_id'],
                                          result['region_id'],
                                          result['date_time'])
        except Exception as e:
            LOG.exception("Some exceptions happen when deducting order: %s, "
                          "for reason: %s", order_id, e)

    def _create_bill(self, ctxt, order_id, action_time, remarks):
        # create a bill
        result = self.gclient.create_bill(order_id, action_time,
                                          remarks)

        # Account is charged but order is still owed
        if result['type'] == const.BILL_OWED_ACCOUNT_CHARGED:
            self._delete_date_job(order_id)

        self._create_cron_job(order_id, action_time=action_time)

    def _close_bill(self, ctxt, order_id, action_time):
        result = self.gclient.close_bill(order_id, action_time)
        self._delete_cron_job(order_id)
        return result

    def get_apsched_jobs_count(self, ctxt):
        """Get scheduled jobs number
        """
        hourly_job_count = 0
        monthly_job_count = 0
        date_job_count = 0
        days_30_job_count = 0

        jobs = self.apsched.get_jobs()

        for job in jobs:
            if job.id.startswith('30-days'):
                days_30_job_count += 1
            elif job.id.startswith('cron'):
                hourly_job_count += 1
            elif job.id.startswith('date'):
                date_job_count += 1
            elif job.id.startswith('monthly'):
                monthly_job_count += 1
        return (hourly_job_count, monthly_job_count,
                date_job_count, days_30_job_count)


    def resource_created(self, ctxt, order_id, action_time, remarks):
        with self._get_lock(order_id):
            LOG.debug('Resource created, its order_id: %s, action_time: %s',
                      order_id, action_time)
            self._create_bill(ctxt, order_id, action_time, remarks)

    def resource_created_again(self, ctxt, order_id, action_time, remarks):
        with self._get_lock(order_id):
            LOG.debug("Resource created again, its order_id: %s, "
                      "action_time: %s", order_id, action_time)
            self._create_bill(ctxt, order_id, action_time, remarks)

    def resource_deleted(self, ctxt, order_id, action_time, remarks):
        with self._get_lock(order_id):
            LOG.debug('Resource deleted, its order_id: %s, action_time: %s',
                      order_id, action_time)
            result = self._close_bill(ctxt, order_id, action_time)

            # Delete date job of owed resource
            if result['resource_owed']:
                self._delete_date_job(order_id)

            # Change order status
            self.gclient.change_order(order_id, const.STATE_DELETED)

            # create a bill that tell people the resource has been deleted
            self.gclient.create_bill(order_id,
                                     action_time=action_time,
                                     remarks=remarks,
                                     end_time=action_time)

            # delete the date job if the order has a 30-days date job
            self._delete_30_days_job(order_id)

            # delete order lock
            self._delete_lock(order_id)

    def resource_stopped(self, ctxt, order_id, action_time, remarks):
        with self._get_lock(order_id):
            LOG.debug('Resource stopped, its order_id: %s, action_time: %s',
                      order_id, action_time)

            result = self._close_bill(ctxt, order_id, action_time)
            # Delete date job of owed resource
            if result['resource_owed']:
                self._delete_date_job(order_id)
            self.gclient.change_order(order_id, const.STATE_STOPPED)

            # create a bill that tell people the resource has been stopped
            self.gclient.create_bill(order_id,
                                     action_time=action_time,
                                     remarks=remarks,
                                     end_time=action_time)

    def resource_started(self, ctxt, order_id, action_time, remarks):
        with self._get_lock(order_id):
            LOG.debug('Resource created, its order_id: %s, action_time: %s',
                      order_id, action_time)
            self.gclient.close_bill(order_id, action_time)
            self.gclient.change_order(order_id, const.STATE_RUNNING)
            self._create_bill(ctxt, order_id, action_time, remarks)

    def resource_changed(self, ctxt, order_id, action_time, change_to,
                         remarks):
        with self._get_lock(order_id):
            LOG.debug("Resource changed, its order_id: %s, action_time: %s, "
                      "will change to: %s", order_id, action_time, change_to)
            # close the old bill
            self._close_bill(ctxt, order_id, action_time)

            # change the order's unit price and its active subscriptions
            self.gclient.change_order(order_id, change_to)

            # create a new bill for the updated order
            self._create_bill(ctxt, order_id, action_time, remarks)

            # delete the date job if the order has a 30-days date job
            self._delete_30_days_job(order_id)

    def resource_resized(self, ctxt, order_id, action_time, quantity, remarks):
        with self._get_lock(order_id):
            LOG.debug("Resource resized, its order_id: %s, action_time: %s, "
                      "will resize to: %s", order_id, action_time, quantity)
            # close the old bill
            self._close_bill(ctxt, order_id, action_time)

            # change subscirption's quantity
            self.gclient.change_subscription(order_id,
                                             quantity, const.STATE_RUNNING)

            # change the order's unit price and its active subscriptions
            self.gclient.change_order(order_id,
                                      const.STATE_RUNNING)

            # create a new bill for the updated order
            self._create_bill(ctxt, order_id, action_time, remarks)

    def instance_stopped(self, ctxt, order_id, action_time):
        """Instance stopped for a month continuously will not be charged

        """
        with self._get_lock(order_id):
            LOG.debug("Instance stopped, its order_id: %s, action_time: %s",
                      order_id, action_time)

            # close the old bill
            self._close_bill(ctxt, order_id, action_time)

            # Caculate cron_time after 30 days from now
            action_time = timeutils.parse_strtime(action_time,
                                                  fmt=TIMESTAMP_TIME_FORMAT)
            cron_time = action_time + datetime.timedelta(days=30)

            # change the order's unit price and its active subscriptions
            self.gclient.change_order(order_id,
                                      const.STATE_STOPPED_IN_30_DAYS,
                                      cron_time=cron_time,
                                      first_change_to=const.STATE_STOPPED)

            # create a bill cross 30 days
            self.gclient.create_bill(order_id,
                                     action_time=action_time,
                                     remarks="Instance Has Been Stopped",
                                     end_time=cron_time)

            # create a date job to change order unit price after 30 days
            # let this action execute 1 hour earlier to ensure unit price
            # be changed before pre deduct
            self._create_date_job_after_30_days(
                order_id, cron_time - datetime.timedelta(hours=1))

            # create a cron job that will execute after 30 days
            self._create_cron_job(order_id, start_date=cron_time)

    def instance_resized(self, ctxt, order_id, action_time,
                         new_flavor, old_flavor,
                         service, region_id, remarks):
        """Instance resized, update the flavor subscription, and change order

        NOTE(suo): This method will not use right now, because only stopped
                   instance can executes resize command, and stopped instance
                   is not charged for a month. So, just change subscription and
                   order in waiter is enough, should not close/create bill for
                   the resource in master
        """
        with self._get_lock(order_id):
            LOG.debug("Instance resized, its order_id: %s, action_time: %s",
                      order_id, action_time)

            # close the old bill
            self._close_bill(ctxt, order_id, action_time)

            # change subscirption's quantity
            self.gclient.change_flavor_subscription(order_id,
                                                    new_flavor, old_flavor,
                                                    service, region_id,
                                                    const.STATE_RUNNING)

            # change the order's unit price and its active subscriptions
            self.gclient.change_order(order_id,
                                      const.STATE_RUNNING)

            # create a new bill for the updated order
            self._create_bill(ctxt, order_id, action_time, remarks)

    def clean_date_jobs(self):
        LOG.warn('Doing clean date jobs')
        orders = self.gclient.get_active_orders(
            charged=True, region_id=cfg.CONF.region_name)

        order_ids = []
        for order in orders:
            order_ids.append(order['order_id'])
            self._delete_date_job(order['order_id'])

        if order_ids:
            self.gclient.reset_charged_orders(order_ids)

    def delete_sched_jobs(self, ctxt, order_id):
        self._delete_cron_job(order_id)
        self._delete_monthly_job(order_id)
        self._delete_date_job(order_id)
        self._delete_30_days_job(order_id)

    def change_monthly_job_time(self, ctxt, order_id, run_date,
                                clear_date_jobs=None):
        if isinstance(run_date, basestring):
            run_date = timeutils.parse_isotime(run_date)
        self._delete_monthly_job(order_id)
        self._create_monthly_job(order_id, run_date)
        if clear_date_jobs:
            self._delete_date_job(order_id)
            self._delete_30_days_job(order_id)

    def create_monthly_job(self, ctxt, order_id, run_date):
        """Create a date job for monthly/yearly billing order
        """
        if isinstance(run_date, basestring):
            run_date = timeutils.parse_isotime(run_date)
        self._create_monthly_job(order_id, run_date)


def master():
    service.prepare_service()
    os_service.launch(MasterService()).wait()
