import datetime
import time

from apscheduler.schedulers import background  # noqa
from oslo.config import cfg  # noqa
import pytz

from gringotts.checker import notifier
from gringotts.client import client
from gringotts import constants as const
from gringotts import context
from gringotts import coordination
from gringotts import master
from gringotts.openstack.common import log
from gringotts.openstack.common import service as os_service
from gringotts.openstack.common import timeutils
from gringotts.openstack.common import uuidutils
from gringotts import service
from gringotts import services
from gringotts.services import alert
from gringotts.services import keystone
from gringotts import utils


LOG = log.getLogger(__name__)
TIMESTAMP_TIME_FORMAT = '%Y-%m-%d %H:%M:%S.%f'
ISO8601_UTC_TIME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'


OPTS = [
    cfg.BoolOpt('try_to_fix',
                default=False,
                help='If found some exceptio, we try to fix it or not'),
    cfg.IntOpt('notifier_level',
               default=0,
               help='The level of the notifier will perform on, there are'
                    '3 levels: 0.log  1.log&email  2.log&email&sms'),
    cfg.IntOpt('days_to_owe',
               default=7,
               help='Days before user will owe'),
    cfg.BoolOpt('enable_center_jobs',
                default=True,
                help='Enable the interval jobs that run in center regions'),
    cfg.BoolOpt('enable_non_center_jobs',
                default=True,
                help='Enable the interval jobs that run in non center '
                     'regions'),
    cfg.StrOpt('support_email',
               help="The cloud manager email"),
    cfg.BoolOpt('send_email_to_sales',
                default=False,
                help='disable the function of sending email to sales'),
    cfg.StrOpt('recharge_url',
               default="https://console.ustack.com/bill/account_charge",
               help="The recharge url"),
    cfg.StrOpt('order_recharge_url',
               default="https://console.ustack.com/bill/order",
               help="The order recharge url")

]

cfg.CONF.register_opts(OPTS, group="checker")


class Situation2Item(object):
    def __init__(self, order_id, resource_type, action_time, change_to,
                 project_id):
        self.order_id = order_id
        self.resource_type = resource_type
        self.action_time = action_time
        self.change_to = change_to
        self.project_id = project_id

    def __eq__(self, other):
        return (self.order_id == other.order_id and
                self.change_to == other.change_to)

    def __repr__(self):
        return "%s:%s" % (self.other_id, self.change_to)


class Situation3Item(object):
    def __init__(self, order_id, resource_created_at, project_id):
        self.order_id = order_id
        self.resource_created_at = resource_created_at
        self.project_id = project_id

    def __eq__(self, other):
        return self.order_id == other.order_id

    def __repr__(self):
        return self.order_id


class Situation4Item(object):
    def __init__(self, order_id, deleted_at, project_id):
        self.order_id = order_id
        self.deleted_at = deleted_at
        self.project_id = project_id

    def __eq__(self, other):
        return self.order_id == other.order_id

    def __repr__(self):
        return self.order_id


class Situation5Item(object):
    def __init__(self, order_id, resource, unit_price, project_id):
        self.order_id = order_id
        self.resource = resource
        self.unit_price = unit_price
        self.project_id = project_id

    def __eq__(self, other):
        return (self.order_id == other.order_id and
                self.resource == other.resource)

    def __repr__(self):
        return self.order_id


class Situation6Item(object):
    def __init__(self, user_id, domain_id, project_id=None):
        self.user_id = user_id
        self.domain_id = domain_id
        self.project_id = project_id

    def __eq__(self, other):
        return self.user_id == other.user_id

    def __repr__(self):
        return self.user_id


class CheckerService(os_service.Service):

    PARTITIONING_GROUP_NAME = 'gringotts_checker'

    def __init__(self, *args, **kwargs):
        self.region_name = cfg.CONF.region_name
        self.gclient = client.get_client()
        self.master_api = master.API()
        self.ctxt = context.get_admin_context()
        self.notifier = notifier.NotifierService(
            cfg.CONF.checker.notifier_level)

        job_defaults = {
            'misfire_grace_time': 604800,
            'coalesce': False,
            'max_instances': 24,
        }
        self.apsched = background.BackgroundScheduler(
            job_defaults=job_defaults,
            timezone=pytz.utc)

        self.RESOURCE_LIST_METHOD = services.RESOURCE_LIST_METHOD
        self.DELETE_METHOD_MAP = services.DELETE_METHOD_MAP
        self.STOP_METHOD_MAP = services.STOP_METHOD_MAP
        self.RESOURCE_STOPPED_STATE = services.RESOURCE_STOPPED_STATE
        self.RESOURCE_GET_MAP = services.RESOURCE_GET_MAP

        # NOTE(suo): Import waiter plugins to invoke register_class methods.
        # Don't import this in module level, because it need to read
        # config file, so it should be imported after service initialization
        from gringotts.waiter import plugins  # noqa

        self.RESOURCE_CREATE_MAP = services.RESOURCE_CREATE_MAP

        super(CheckerService, self).__init__(*args, **kwargs)

    def start(self):
        super(CheckerService, self).start()
        # NOTE(suo): We should create coordinator and member_id in start(),
        # because child process will execute start() privately, thus every
        # child process will have its own coordination connection.
        self.member_id = uuidutils.generate_uuid()
        self.partition_coordinator = coordination.PartitionCoordinator(
            self.member_id)
        self.partition_coordinator.start()
        self.partition_coordinator.join_group(self.PARTITIONING_GROUP_NAME)

        if self.partition_coordinator.is_active():
            # NOTE(suo): Don't use loopingcall to do heartbeat, it will hang
            # if tooz driver restarts
            self.apsched.add_job(self.partition_coordinator.heartbeat,
                                 'interval',
                                 seconds=cfg.CONF.coordination.heartbeat)

        # NOTE(suo): apscheduler must be started in child process
        self.apsched.start()
        self.load_jobs()
        self.tg.add_timer(604800, lambda: None)

    def load_jobs(self):
        """Load cron jobs

        Every check point is an apscheduler job that scheduled to different
        time with different period
        """
        # One minutes delay to start jobs
        start_date = (datetime.datetime.utcnow() +
                      datetime.timedelta(seconds=60))
        non_center_jobs = [
            (self.check_if_resources_match_orders, 1, start_date),
            (self.check_if_owed_resources_match_owed_orders, 1, start_date),
            (self.check_if_cronjobs_match_orders, 1, start_date),
        ]

        nine_clock = self._absolute_9_clock()
        center_jobs = [
            (self.check_owed_hour_resources_and_notify, 24, nine_clock),
            (self.check_owed_order_resources_and_notify, 24, nine_clock),
            # (self.check_user_to_account, 2, start_date),
            # (self.check_project_to_project, 2, start_date),
        ]

        if cfg.CONF.checker.enable_non_center_jobs:
            for job, period, start_date in non_center_jobs:
                self.apsched.add_job(job,
                                     'interval',
                                     hours=period,
                                     start_date=start_date)

        if cfg.CONF.checker.enable_center_jobs:
            for job, period, start_date in center_jobs:
                self.apsched.add_job(job,
                                     'interval',
                                     hours=period,
                                     start_date=start_date)

        if cfg.CONF.checker.send_email_to_sales:
            self.apsched.add_job(self.send_accounts_to_sales,
                                 'cron',
                                 month='1-12', day='last',
                                 hour='23', minute='59', second='59')
        LOG.warn("[%s] Load jobs successfully, waiting for other checkers "
                 "to join the group...", self.member_id)

    def _absolute_9_clock(self):
        nowutc = datetime.datetime.utcnow()
        nowutc_time = nowutc.time()
        nowutc_date = nowutc.date()
        clock = datetime.time(1, 0, 0)
        if nowutc_time > clock:
            nowutc_date = nowutc_date + datetime.timedelta(hours=24)
        return datetime.datetime.combine(nowutc_date, clock)

    def send_accounts_to_sales(self):
        period_end_time = datetime.datetime.utcnow()
        period_start_time = datetime.datetime(period_end_time.year,
                                              period_end_time.month,
                                              1, 0, 0, 0)
        try:
            accounts = self._assigned_accounts()
        except Exception:
            LOG.exception('Failed to get assigned accounts')
            return

        LOG.warn("[%s] Sending accounts to sales, assigned accounts "
                 "number: %s", self.member_id, len(accounts))

        email_bodies = {}
        sales_email_name = {}

        for account in accounts:
            sales_id = account['sales_id']
            if not sales_email_name.get(sales_id):
                sales = keystone.get_uos_user(sales_id)
                if not sales:
                    continue

                sales_email = sales['email']
                sales_name = sales.get('real_name') or sales['name']

                sales_email_name[sales_id] = (sales_email, sales_name)

            uos_user = keystone.get_uos_user(account['user_id'])
            if not uos_user:
                continue

            # get name, email, mobile, company of the account
            name = uos_user.get('real_name') or uos_user['name']
            email = uos_user.get('email')
            mobile = uos_user.get('mobile_number') or 'unknown'
            company = uos_user.get('company') or 'unknown'

            # get the type of the user, eg: Main account
            users = keystone.get_account_type(
                value=account['user_id'])['users']
            if users:
                if not users[0]['enabled']:
                    user_type = u'Inactivated User'
                elif users[0]['is_domain_owner']:
                    user_type = u'Main account'
                else:
                    user_type = u'Sub account'
            else:
                user_type = u'Unknown'

            # get the status of the account
            status = u'Enabled' if uos_user['enabled'] else u"Nonactivated"

            # get the register time of the account
            created_at = utils.format_datetime(
                uos_user.get('created_at') or account['created_at'])

            # get the charge, coupon, bonus of the account
            charge = 0
            coupon = 0
            bonus = 0
            charges = self.gclient.get_charges(account['user_id'])
            for one in charges:
                if one['type'] == 'bonus':
                    bonus += float(one['value'])
                elif one['type'] == 'money':
                    charge += float(one['value'])
                elif one['type'] == 'coupon':
                    coupon += float(one['value'])
                else:
                    LOG.info('%s is unknown charge type!' % one['type'])

            # get the balance of the account
            balance = round(float(account['balance']), 4)

            # get consumption in a period, the period is a month for the moment
            period_consumption = self.gclient.get_orders_summary(
                account['user_id'],
                period_start_time,
                period_end_time)
            period_consumption = round(
                float(period_consumption['total_price']), 4)

            # predict the consumption per day
            predict_day_consumption = self.gclient.get_consumption_per_day(
                account['user_id'])
            predict_day_consumption = round(
                float(predict_day_consumption['price_per_day']), 4)

            # get the days that the balance can support
            remain_consumption_day = 0
            if predict_day_consumption:
                remain_consumption_day = int(balance / predict_day_consumption)

            # get the capital consumption
            total_charge = charge + coupon + bonus
            capital_consumption = 0
            if total_charge:
                capital_consumption = round(
                    (charge / total_charge) * period_consumption, 4)

            if sales_email not in email_bodies:
                email_bodies[sales_email] = []

            email_bodies[sales_email].append((name, email, mobile, company,
                                              user_type, status, created_at,
                                              charge, bonus, coupon, balance,
                                              predict_day_consumption,
                                              remain_consumption_day,
                                              period_consumption,
                                              capital_consumption))

        self.notifier.send_account_info(self.ctxt, email_bodies,
                                        sales_email_name)

    def _check_resource_to_order(self, resource, resource_to_order,
                                 bad_resources, try_to_fix):
        try:
            order = resource_to_order[resource.id]
        except KeyError:
            # Situation 1: There may exist resources that have no orders
            # NOTE(suo): The resource billed by month/year may also has no
            # order, but for now, we couldn't know which billing type it is
            # only from the GET resource method, on this occasion, we take
            # this resource as the hourly billing type, then create the order
            # in auto-fix process
            if resource.status == const.STATE_ERROR:
                bad_resources.append(resource)
                return
            if not resource.is_bill:
                return
            try_to_fix['1'].append(resource)
        else:
            # Situation 2: There may exist resource whose status doesn't match
            # with its order's
            if resource.status == const.STATE_ERROR:
                bad_resources.append(resource)
            elif order['unit'] in ['month', 'year']:
                # if the order is billed by month or year, we don't check
                # it for now, just pass, and set it to checked later
                pass
            elif (resource.resource_type == const.RESOURCE_LISTENER and
                  resource.admin_state != order['status']):
                # for loadbalancer listener
                action_time = utils.format_datetime(timeutils.strtime())
                try_to_fix['2'].append(Situation2Item(order['order_id'],
                                                      resource.resource_type,
                                                      action_time,
                                                      resource.admin_state,
                                                      resource.project_id))
            elif (resource.resource_type != const.RESOURCE_LISTENER and
                  resource.status != order['status']):
                action_time = utils.format_datetime(timeutils.strtime())
                try_to_fix['2'].append(Situation2Item(order['order_id'],
                                                      resource.resource_type,
                                                      action_time,
                                                      resource.status,
                                                      resource.project_id))
            # Situation 3: Resource's order has been created, but its bill not
            # be created by master
            elif (not order['cron_time'] and
                  order['status'] != const.STATE_STOPPED):
                try_to_fix['3'].append(Situation3Item(order['order_id'],
                                                      resource.created_at,
                                                      resource.project_id))
            # Situation 5: The order's unit_price is different from the
            # resource's actual price
            else:
                resource_status = (resource.admin_state
                                   if hasattr(resource, 'admin_state')
                                   else resource.status)
                unit_price = (
                    self.RESOURCE_CREATE_MAP[resource.resource_type].\
                    get_unit_price(order['order_id'],
                                   resource.to_message(),
                                   resource_status,
                                   cron_time=order['cron_time']))
                order_unit_price = utils._quantize_decimal(order['unit_price'])
                if unit_price is not None and unit_price != order_unit_price:
                    try_to_fix['5'].append(Situation5Item(order['order_id'],
                                                          resource,
                                                          unit_price,
                                                          resource.project_id))
            resource_to_order[resource.id]['checked'] = True

    def _check_order_to_resource(self, resource_id, order, try_to_fix):
        # Situation 4: The resource of the order has been deleted
        deleted_at = utils.format_datetime(timeutils.strtime())
        try_to_fix['4'].append(Situation4Item(order['order_id'],
                                              deleted_at,
                                              order['project_id']))

    def _check_if_resources_match_orders(self, bad_resources, try_to_fix,
                                         projects):
        """Check one time to collect orders/resources that may need to fix and
        notify
        """
        for project in projects:
            if project['project_id'] in cfg.CONF.ignore_tenants:
                continue
            # Get all active orders
            resource_to_order = {}
            orders = self.gclient.get_active_orders(
                region_id=self.region_name,
                project_id=project['project_id'])
            for order in orders:
                if not isinstance(order, dict):
                    order = order.as_dict()
                order['checked'] = False
                resource_to_order[order['resource_id']] = order

            # Check resource to order
            for method in self.RESOURCE_LIST_METHOD:
                resources = method(project['project_id'],
                                   region_name=self.region_name,
                                   project_name=project['project_name'])
                for resource in resources:
                    self._check_resource_to_order(resource,
                                                  resource_to_order,
                                                  bad_resources,
                                                  try_to_fix)
            # Check order to resource
            for resource_id, order in resource_to_order.items():
                if order['checked']:
                    continue
                self._check_order_to_resource(resource_id, order, try_to_fix)

    def _assigned_projects(self):
        """Only check the active projects
        """
        projects = list(self.gclient.get_projects(type='simple',
                                                  duration='30d'))
        return self.partition_coordinator.extract_my_subset(
            self.PARTITIONING_GROUP_NAME, projects)

    def check_if_resources_match_orders(self):
        """Check if resources match with orders

        There are 5 situations in every check:
        * There exist resources that are not billed
        * There exist resources whose status don't match with its order's
          status
        * There exist resource's order has been created, but its bill not be
          created by master
        * There exist active orders that their resource has been deleted
        * There exist order's unit_price is different from the resource's
          actual price

        We do this check every one hour.

        For auto-recovery, we only do this if we can ensure all services are
        ok, or it will skip this circle, do the check and auto-recovery in the
        next circle.
        """
        bad_resources_1 = []
        bad_resources_2 = []
        try_to_fix_1 = {'1': [], '2': [], '3': [], '4': [], '5': []}
        try_to_fix_2 = {'1': [], '2': [], '3': [], '4': [], '5': []}

        projects = self._assigned_projects()
        LOG.warn("[%s] Checking if resources match with orders, assigned "
                 "projects number: %s", self.member_id, len(projects))

        try:
            self._check_if_resources_match_orders(bad_resources_1,
                                                  try_to_fix_1,
                                                  projects)
            time.sleep(30)
            self._check_if_resources_match_orders(bad_resources_2,
                                                  try_to_fix_2,
                                                  projects)
        except Exception:
            LOG.exception("Some exceptions occurred when checking whether "
                          "resources match with orders, skip this checking "
                          "circle.")
            return

        # NOTE(suo): We only do the auto-fix when there is not any exceptions

        # Alert bad resources
        bad_resources = [x for x in bad_resources_2 if x in bad_resources_1]
        if bad_resources:
            alert.alert_bad_resources(bad_resources)

        # Fix bad resources and orders
        try_to_fix_situ_1 = [x for x in try_to_fix_2['1']
                             if x in try_to_fix_1['1']]
        try_to_fix_situ_2 = [x for x in try_to_fix_2['2']
                             if x in try_to_fix_1['2']]
        try_to_fix_situ_3 = [x for x in try_to_fix_2['3']
                             if x in try_to_fix_1['3']]
        try_to_fix_situ_4 = [x for x in try_to_fix_2['4']
                             if x in try_to_fix_1['4']]
        try_to_fix_situ_5 = [x for x in try_to_fix_2['5']
                             if x in try_to_fix_1['5']]

        # Situation 1
        for resource in try_to_fix_situ_1:
            LOG.warn("[%s] Situation 1: In project(%s), the resource(%s) "
                     "has no order",
                     self.member_id, resource.project_id, resource.id)
            if cfg.CONF.try_to_fix:
                create_cls = self.RESOURCE_CREATE_MAP[resource.resource_type]
                create_cls.process_notification(resource.to_message(),
                                                resource.status)
        # Situation 2
        for item in try_to_fix_situ_2:
            LOG.warn("[%s] Situation 2: In project(%s), the order(%s) and "
                     "its resource's status doesn't match",
                     self.member_id, item.project_id, item.order_id)
            if cfg.CONF.try_to_fix:
                if (item.resource_type == const.RESOURCE_INSTANCE and
                        item.change_to == const.STATE_STOPPED):
                    self.master_api.instance_stopped(self.ctxt,
                                                     item.order_id,
                                                     item.action_time)
                else:
                    self.master_api.resource_changed(self.ctxt,
                                                     item.order_id,
                                                     item.action_time,
                                                     change_to=item.change_to,
                                                     remarks="System Adjust")
        # Situation 3
        for item in try_to_fix_situ_3:
            LOG.warn("[%s] Situation 3: In project(%s), the order(%s) "
                     "has no bills",
                     self.member_id, item.project_id, item.order_id)
            if cfg.CONF.try_to_fix:
                self.master_api.resource_created_again(
                    self.ctxt,
                    item.order_id,
                    item.resource_created_at,
                    "Sytstem Adjust")
        # Situation 4
        for item in try_to_fix_situ_4:
            LOG.warn("[%s] Situation 4: In project(%s), the order(%s)'s "
                     "resource has been deleted.",
                     self.member_id, item.project_id, item.order_id)
            if cfg.CONF.try_to_fix:
                self.master_api.resource_deleted(self.ctxt,
                                                 item.order_id,
                                                 item.deleted_at,
                                                 "Resource Has Been Deleted")
        # Situation 5
        for item in try_to_fix_situ_5:
            LOG.warn("[%s] Situation 5: In project(%s), the order(%s)'s "
                     "unit_price is wrong, should be %s",
                     self.member_id, item.project_id,
                     item.order_id, item.unit_price)
            if cfg.CONF.try_to_fix:
                resource_type = item.resource.resource_type
                create_cls = self.RESOURCE_CREATE_MAP[resource_type]
                create_cls.change_unit_price(item.resource.to_message(),
                                             item.resource.status,
                                             item.order_id)

    def _check_if_owed_resources_match_owed_orders(self,
                                                   should_stop_resources,
                                                   should_delete_resources,
                                                   projects):
        for project in projects:
            orders = list(self.gclient.get_active_orders(
                region_id=self.region_name,
                project_id=project['project_id'],
                owed=True))
            if not orders:
                continue
            for order in orders:
                if isinstance(order['date_time'], basestring):
                    order['date_time'] = timeutils.parse_strtime(
                        order['date_time'],
                        fmt=ISO8601_UTC_TIME_FORMAT)
                if isinstance(order['cron_time'], basestring):
                    order['cron_time'] = timeutils.parse_strtime(
                        order['cron_time'],
                        fmt=ISO8601_UTC_TIME_FORMAT)

                resource = self.RESOURCE_GET_MAP[order['type']](
                    order['resource_id'],
                    region_name=self.region_name)

                if not resource:
                    LOG.warn('The resource of the order(%s) not exists',
                             order)
                    continue

                now = datetime.datetime.utcnow()
                if order['date_time'] < now:
                    should_delete_resources.append(resource)
                elif order['unit'] in ['month', 'year']:
                    continue
                elif (order['type'] == const.RESOURCE_FLOATINGIP and
                        not resource.is_reserved and order['owed']):
                    should_delete_resources.append(resource)
                elif (resource.resource_type == const.RESOURCE_LISTENER and
                        not resource.is_last_up and
                        resource.admin_state !=
                        self.RESOURCE_STOPPED_STATE[order['type']]):
                    should_stop_resources.append(resource)
                elif (resource.resource_type != const.RESOURCE_LISTENER and
                        resource.status !=
                        self.RESOURCE_STOPPED_STATE[order['type']]):
                    should_stop_resources.append(resource)

    def check_if_owed_resources_match_owed_orders(self):
        should_stop_resources_1 = []
        should_stop_resources_2 = []
        should_delete_resources_1 = []
        should_delete_resources_2 = []

        projects = self._assigned_projects()
        LOG.warn("[%s] Checking if owed resources match with owed orders, "
                 "assigned project number: %s",
                 self.member_id, len(projects))

        try:
            self._check_if_owed_resources_match_owed_orders(
                should_stop_resources_1,
                should_delete_resources_1,
                projects)
            time.sleep(30)
            self._check_if_owed_resources_match_owed_orders(
                should_stop_resources_2,
                should_delete_resources_2,
                projects)
        except Exception:
            LOG.exception("Some exceptions occurred when checking whether "
                          "owed resources match with owed orders, skip this "
                          "checking circle.")
            return

        # NOTE(suo): We only do the auto-fix when there is not any exceptions

        should_stop_resources = [x for x in should_stop_resources_2
                                 if x in should_stop_resources_1]
        should_delete_resources = [x for x in should_delete_resources_2
                                   if x in should_delete_resources_1]

        for resource in should_stop_resources:
            LOG.warn("[%s] The resource(%s) is owed, should be stopped",
                     self.member_id, resource)
            if cfg.CONF.try_to_fix:
                try:
                    self.STOP_METHOD_MAP[resource.resource_type](
                        resource.id, self.region_name)
                except Exception:
                    LOG.warn("Fail to stop the owed resource(%s)" % resource)

        for resource in should_delete_resources:
            LOG.warn("[%s] The resource(%s) is reserved for its full days, "
                     "should be deleted", self.member_id, resource)
            if cfg.CONF.try_to_fix:
                try:
                    self.DELETE_METHOD_MAP[resource.resource_type](
                        resource.id, self.region_name)
                except Exception:
                    LOG.warn("Fail to delete the owed resource(%s)" % resource)

    def check_if_cronjobs_match_orders(self):
        """Check if cron jobs match with orders

        There are 4 kinds of jobs:
            * hourly cron jobs
            * monthly cron jobs
            * date jobs
            * 30 days date jobs

        We should separately get these kinds of jobs from master service and
        gclient to compare them.
        """
        LOG.warn('[%s] Checking if cronjobs match with orders', self.member_id)
        try:
            # As hourly order always has cron job no matter it is owed or not,
            # so we should get all hourly orders count
            hourly_order_count = self.gclient.get_active_order_count(
                self.region_name, bill_methods=['hour'])

            # NOTE(suo): owed="" means owed=False, because owed monthly order
            # has no monthly cron job, so should only get the not owed monthly
            # orders count.
            monthly_order_count = self.gclient.get_active_order_count(
                self.region_name, bill_methods=['month', 'year'], owed="")

            # hourly and monthly order have the same owed logic, so every
            # owed resource should have a date job
            owed_order_count = self.gclient.get_active_order_count(
                self.region_name, owed=True)

            # stopped order means the instances that have been stopped
            # within 30 days
            stopped_order_count = self.gclient.get_stopped_order_count(
                self.region_name, 
                type=const.RESOURCE_INSTANCE,
                bill_methods=['hour'])

            (hourly_job_count, monthly_job_count,
             date_job_count, days_30_job_count) = \
                    self.master_api.get_apsched_jobs_count(self.ctxt)

            LOG.warn("[%s] Checked, There are %s hourly jobs, and %s "
                     "hourly orders",
                     self.member_id, hourly_job_count, hourly_order_count)

            LOG.warn("[%s] Checked, There are %s monthly jobs, and %s "
                     "not-owed monthly orders",
                     self.member_id, monthly_job_count, monthly_order_count)

            LOG.warn("[%s] Checked, There are %s date jobs, and %s "
                     "owed orders",
                     self.member_id, date_job_count, owed_order_count)

            LOG.warn("[%s] Checked, There are %s 30-days jobs, and %s "
                     "stopped instance orders",
                     self.member_id, days_30_job_count, stopped_order_count)

        except Exception:
            LOG.exception("Some exceptions occurred when checking whether "
                          "cron jobs match with orders or not")

    def _assigned_accounts(self):
        accounts = list(self.gclient.get_accounts(duration='30d'))
        return self.partition_coordinator.extract_my_subset(
            self.PARTITIONING_GROUP_NAME, accounts)

    def check_owed_hour_resources_and_notify(self):  # noqa
        """Check owed hour-billing resources and notify them

        Get owed accounts, send them sms/email notifications.
        """
        try:
            accounts = self._assigned_accounts()
        except Exception:
            LOG.exception("Fail to get assigned accounts")
            accounts = []
        LOG.warn("[%s] Notifying owed accounts, assigned accounts number: %s",
                 self.member_id, len(accounts))

        bill_methods=['hour',]

        for account in accounts:
            try:
                if not isinstance(account, dict):
                    account = account.as_dict()

                if account['level'] == 9:
                    continue

                if account['owed']:
                    orders = list(
                        self.gclient.get_active_orders(
                            user_id=account['user_id'],
                            owed=True,
                            bill_methods=bill_methods)
                    )
                    if not orders:
                        continue

                    contact = keystone.get_uos_user(account['user_id'])
                    _projects = self.gclient.get_projects(
                        user_id=account['user_id'],
                        type='simple')

                    orders_dict = {}
                    for project in _projects:
                        orders_dict[project['project_id']] = []

                    for order in orders:
                        # check if the resource exists
                        resource = self.RESOURCE_GET_MAP[order['type']](
                            order['resource_id'],
                            region_name=order['region_id'])
                        if not resource:
                            # alert that the resource not exists
                            LOG.warn("[%s] The resource(%s|%s) has been "
                                     "deleted",
                                     self.member_id,
                                     order['type'], order['resource_id'])
                            alert.wrong_billing_order(order,
                                                      'resource_deleted')
                            continue

                        order_d = {}
                        order_d['order_id'] = order['order_id']
                        order_d['region_id'] = order['region_id']
                        order_d['resource_id'] = order['resource_id']
                        order_d['resource_name'] = order['resource_name']
                        order_d['type'] = order['type']

                        if isinstance(order['date_time'], basestring):
                            order['date_time'] = timeutils.parse_strtime(
                                order['date_time'],
                                fmt=ISO8601_UTC_TIME_FORMAT)

                        now = datetime.datetime.utcnow()
                        reserved_days = (order['date_time'] - now).days
                        if reserved_days < 0:
                            LOG.warn("[%s] The order %s reserved_days is "
                                     "less than 0",
                                     self.member_id, order['order_id'])
                            reserved_days = 0
                        order_d['reserved_days'] = reserved_days

                        order_d['date_time'] = timeutils.strtime(
                            order['date_time'],
                            fmt=ISO8601_UTC_TIME_FORMAT)

                        orders_dict[order['project_id']].append(order_d)

                    projects = []
                    for project in _projects:
                        if orders_dict[project['project_id']]:
                            adict = {}
                            adict['project_id'] = project['project_id']
                            adict['project_name'] = project['project_name']
                            adict['orders'] = (orders_dict[
                                               project['project_id']])
                            projects.append(adict)

                    if not projects:
                        continue

                    reserved_days = utils.cal_reserved_days(account['level'])
                    account['reserved_days'] = reserved_days
                    country_code = contact.get("country_code") or "86"
                    language = "en_US" if country_code != '86' else "zh_CN"
                    self.notifier.notify_has_owed(self.ctxt, account, contact,
                                                  projects, language=language)
                else:
                    orders = self.gclient.get_active_orders(
                        user_id=account['user_id'],
                        bill_methods=bill_methods)
                    if not orders:
                        continue

                    _projects = self.gclient.get_projects(
                        user_id=account['user_id'], type='simple')

                    estimation = {}
                    for project in _projects:
                        estimation[project['project_id']] = 0

                    price_per_hour = 0
                    for order in orders:
                        # check if the resource exists
                        resource = self.RESOURCE_GET_MAP[order['type']](
                            order['resource_id'],
                            region_name=order['region_id'])
                        if not resource:
                            # alert that the resource not exists
                            LOG.warn("[%s] The resource(%s|%s) may has been "
                                     "deleted",
                                     self.member_id, order['type'],
                                     order['resource_id'])
                            alert.wrong_billing_order(order,
                                                      'resource_deleted')
                            continue

                        price_per_hour += utils._quantize_decimal(
                            order['unit_price'])
                        estimation[order['project_id']] += \
                            utils._quantize_decimal(order['unit_price'])

                    price_per_day = price_per_hour * 24
                    account_balance = utils._quantize_decimal(
                        account['balance'])

                    if price_per_day == 0:
                        continue

                    days_to_owe_d = float(account_balance / price_per_day)
                    days_to_owe = round(days_to_owe_d)

                    if days_to_owe > cfg.CONF.checker.days_to_owe:
                        continue

                    # caculate projects
                    projects = []
                    for project in _projects:
                        adict = {}
                        adict['project_id'] = project['project_id']
                        adict['project_name'] = project['project_name']
                        adict['estimation'] = str(
                            estimation[project['project_id']] * 24)
                        projects.append(adict)

                    if not projects:
                        continue

                    contact = keystone.get_uos_user(account['user_id'])
                    country_code = contact.get("country_code") or "86"
                    language = "en_US" if country_code != '86' else "zh_CN"
                    self.notifier.notify_before_owed(self.ctxt, account,
                                                     contact, projects,
                                                     str(price_per_day),
                                                     days_to_owe,
                                                     language=language)
            except Exception:
                LOG.exception("Some exceptions occurred when checking owed "
                              "account: %s", account['user_id'])

    def check_owed_order_resources_and_notify(self):  #noqa
        """Check order-billing resources and notify related accounts

        Send sms/email notifications for each has-owed or will-owed order.
        """
        try:
            accounts = self._assigned_accounts()
        except Exception:
            LOG.exception("Fail to get assigned accounts")
            accounts = []
        LOG.warn("[%s] Notifying owed accounts, assigned accounts number: %s",
                 self.member_id, len(accounts))

        bill_methods = ['month', 'year']

        for account in accounts:
            try:
                if not isinstance(account, dict):
                    account = account.as_dict()

                if account['level'] == 9:
                    continue

                contact = keystone.get_uos_user(account['user_id'])
                country_code = contact.get("country_code") or "86"
                language = "en_US" if country_code != '86' else "zh_CN"
                account['reserved_days'] = utils.cal_reserved_days(account['level'])

                orders = list(
                    self.gclient.get_active_orders(
                        user_id=account['user_id'],
                        bill_methods=bill_methods)
                )

                for order in orders:
                    # check if the resource exists
                    resource = self.RESOURCE_GET_MAP[order['type']](
                        order['resource_id'],
                        region_name=order['region_id'])
                    if not resource:
                        # alert that the resource not exists
                        LOG.warn("[%s] The resource(%s|%s) has been "
                                 "deleted",
                                 self.member_id,
                                 order['type'], order['resource_id'])
                        alert.wrong_billing_order(order,
                                                  'resource_deleted')
                        continue

                    order_d = {}
                    order_d['order_id'] = order['order_id']
                    order_d['region_id'] = order['region_id']
                    order_d['resource_id'] = order['resource_id']
                    order_d['resource_name'] = order['resource_name']
                    order_d['type'] = order['type']
                    order_d['owed'] = order['owed']

                    if isinstance(order['date_time'], basestring):
                        order['date_time'] = timeutils.parse_strtime(
                            order['date_time'],
                            fmt=ISO8601_UTC_TIME_FORMAT)

                    if isinstance(order['cron_time'], basestring):
                        order['cron_time'] = timeutils.parse_strtime(
                            order['cron_time'],
                            fmt=ISO8601_UTC_TIME_FORMAT)

                    # if order is owed, reserved_days represent how long resource will be reserved;
                    # if not, reserved_days repesent how long resource will be expired
                    now = datetime.datetime.utcnow()
                    if order['owed']:
                        reserved_days = (order['date_time'] - now).days
                    else:
                        reserved_days = (order['cron_time'] - now).days
                    if reserved_days < 0:
                        LOG.warn("[%s] The order %s reserved_days is "
                                 "less than 0",
                                 self.member_id, order['order_id'])
                        reserved_days = 0
                    order_d['reserved_days'] = reserved_days

                    order_d['date_time'] = timeutils.strtime(
                        order['date_time'],
                        fmt=ISO8601_UTC_TIME_FORMAT)

                    order_d['cron_time'] = timeutils.strtime(
                        order['cron_time'],
                        fmt=ISO8601_UTC_TIME_FORMAT)

                    is_notify_will_owed = (order_d['reserved_days'] <= cfg.CONF.checker.days_to_owe)
                    if order_d['owed'] or (not order_d['owed'] and is_notify_will_owed):
                        self.notifier.notify_order_billing_owed(self.ctxt, account, contact,
                                                                order_d, language=language)

            except Exception:
                LOG.exception("Some exceptions occurred when checking owed "
                              "account: %s", account['user_id'])

    def _figure_out_difference(self, alist, akey, blist, bkey):
        ab = []
        s = 0
        l = len(blist)
        for a in alist:
            for i in range(s, l):
                b = blist[i]
                if getattr(a, akey) == b.get(bkey):
                    s = i
                    break
                if getattr(a, akey) < b.get(bkey) or i == (l - 1):
                    s = i
                    ab.append(a)
                    break
        return ab

    def _check_user_to_account(self):
        accounts = sorted(self.gclient.get_accounts(),
                          key=lambda account: account['user_id'])
        users = sorted(keystone.get_user_list(), key=lambda user: user.id)

        _users = self._figure_out_difference(users, 'id', accounts, 'user_id')
        result = []
        for u in _users:
            result.append(keystone.User(
                u.id, u.domain_id,
                project_id=getattr(u, 'default_project_id', None)))
        return result

    def check_user_to_account(self):
        LOG.warn("[%s] Checking if users in keystone match accounts "
                 "in gringotts", self.member_id)
        try:
            users_1 = self._check_user_to_account()
            time.sleep(30)
            users_2 = self._check_user_to_account()
        except Exception:
            LOG.exception("Some exceptions occurred when checking whether "
                          "users match with account, skip this checking "
                          "circle.")
            return

        # NOTE(suo): We only do the auto-fix when there is not any exceptions

        users = [u for u in users_1 if u in users_2]
        for user in users:
            LOG.warn("[%s] Situation 6: The user(%s) has not been created "
                     "in gringotts", self.member_id, user.user_id)
            if cfg.CONF.try_to_fix:
                create_cls = self.RESOURCE_CREATE_MAP[const.RESOURCE_USER]
                create_cls.process_notification(user.to_message())

    def _check_project_to_project(self):
        _k_projects = keystone.get_projects_by_project_ids()
        _g_projects = self.gclient.get_projects(type='simple')

        k_projects = []
        g_projects = []
        for kp in _k_projects:
            billing_owner = kp['users']['billing_owner']
            k_projects.append(
                keystone.Project(
                    kp['id'],
                    billing_owner.get('id') if billing_owner else None,
                    kp['domain_id']))
        for gp in _g_projects:
            g_projects.append(
                keystone.Project(gp['project_id'],
                                 gp['billing_owner'],
                                 gp['domain_id']))

        # projects in keystone but not in gringotts
        creating_projects = list(set(k_projects) - set(g_projects))

        # projects in gringotts but not in keystone
        deleting_projects = []
        _deleted_projects = list(set(g_projects) - set(k_projects))
        for p in _deleted_projects:
            if self.gclient.get_resources(p.project_id):
                deleting_projects.append(p)

        # projects whose billing owner is not equal to each other
        billing_projects = []  # changing billing owner
        projects_k = sorted(set(g_projects) & set(k_projects),
                            key=lambda p: p.project_id)
        projects_g = sorted(set(k_projects) & set(g_projects),
                            key=lambda p: p.project_id)

        for k, g in zip(projects_k, projects_g):
            if k.billing_owner_id != g.billing_owner_id:
                billing_projects.append(k)

        return (creating_projects, deleting_projects, billing_projects)

    def check_project_to_project(self):
        """Check two situations:

        1. Projects in keystone but not in gringotts, means gringotts didn't
           receive the create project message.
        2. Projects in gringotts but not in keystone still has resources,
           means projects in keystone has been deleted, but its resources
           didn't be deleted
        3. Check the project's billing owner in gringotts matches
           billing_projects owner in keystone
        """
        LOG.warn("[%s] Checking if projects in keystone match projects "
                 "in gringotts", self.member_id)
        try:
            cp_1, dp_1, bp_1 = self._check_project_to_project()
            time.sleep(30)
            cp_2, dp_2, bp_2 = self._check_project_to_project()
        except Exception:
            LOG.exception("Some exceptions occurred when checking whether "
                          "projects match with projects, skip this checking "
                          "circle.")
            return

        # NOTE(suo): We only do the auto-fix when there is not any exceptions

        creating_projects = [p for p in cp_1 if p in cp_2]
        deleting_projects = [p for p in dp_1 if p in dp_2]
        billing_projects = [p for p in bp_1 if p in bp_2]

        for p in creating_projects:
            LOG.warn("[%s] Situation 7: The project(%s) exists in keystone "
                     "but not in gringotts, its billing owner is %s",
                     self.member_id, p.project_id, p.billing_owner_id)
            if cfg.CONF.try_to_fix and p.billing_owner_id:
                create_cls = self.RESOURCE_CREATE_MAP[const.RESOURCE_PROJECT]
                create_cls.process_notification(p.to_message())

        for p in deleting_projects:
            LOG.warn("[%s] Situation 8: The project(%s) has been deleted, "
                     "but its resources has not been cleared",
                     self.member_id, p.project_id)
            if cfg.CONF.try_to_fix:
                try:
                    self.gclient.delete_resources(p.project_id)
                except Exception:
                    LOG.exception("Fail to delete all resources of project %s",
                                  p.project_id)
                    return

        for p in billing_projects:
            LOG.warn("[%s] Situation 9: The project(%s)'s billing owner in "
                     "gringotts is not equal to keystone's, should be: %s",
                     self.member_id, p.project_id, p.billing_owner_id)
            if cfg.CONF.try_to_fix and p.billing_owner_id:
                try:
                    self.gclient.change_billing_owner(p.project_id,
                                                      p.billing_owner_id)
                except Exception:
                    LOG.exception("Fail to change billing owner of project "
                                  "%s to user %s",
                                  p.project_id, p.billing_owner_id)
                    return


def checker():
    service.prepare_service()
    os_service.launch(CheckerService(),
                      workers=cfg.CONF.checker_workers).wait()
