import datetime
import time
from oslo.config import cfg

from apscheduler.scheduler import Scheduler as APScheduler

from gringotts import master
from gringotts import worker
from gringotts import exception
from gringotts import context
from gringotts import utils
from gringotts import constants as const
from gringotts.checker import notifier
from gringotts.service import prepare_service
from gringotts.services import alert
from gringotts.services.keystone import User,Project

from gringotts.waiter import plugins

from gringotts.openstack.common import log
from gringotts.openstack.common import timeutils
from gringotts.openstack.common import service as os_service


LOG = log.getLogger(__name__)
TIMESTAMP_TIME_FORMAT = '%Y-%m-%d %H:%M:%S.%f'
ISO8601_UTC_TIME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'


OPTS = [
    cfg.BoolOpt('try_to_fix',
                default=False,
                help='If found some exceptio, we try to fix it or not'),
    cfg.IntOpt('notifier_level',
               default=0,
               help='The level of the notifier will perform on, there are 3 levels:'
                    '0.log  1.log&email  2.log&email&sms'),
    cfg.IntOpt('days_to_owe',
               default=7,
               help='Days before user will owe'),
    cfg.BoolOpt('enable_center_jobs',
                default=True,
                help='Enable the interval jobs that run in center regions'),
    cfg.BoolOpt('enable_non_center_jobs',
                default=True,
                help='Enable the interval jobs that run in non center regions'),
    cfg.ListOpt('ignore_tenants',
                default=[],
                help="A list of tenant that should not to check"),
    cfg.StrOpt('support_email',
               default='support@unitedstack.com',
               help="The cloud manager email")
]

cfg.CONF.register_opts(OPTS, group="checker")


class Situation2Item(object):
    def __init__(self, order_id, action_time, change_to, project_id):
        self.order_id = order_id
        self.action_time = action_time
        self.change_to = change_to
        self.project_id = project_id

    def __eq__(self, other):
        return self.order_id == other.order_id and self.change_to == other.change_to

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
        return self.order_id == other.order_id and self.resource == other.resource

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

    def __init__(self, *args, **kwargs):
        self.region_name = cfg.CONF.region_name
        self.worker_api = worker.API()
        self.master_api = master.API()
        self.notifier = notifier.NotifierService(cfg.CONF.checker.notifier_level)
        config = {
            'apscheduler.threadpool.max_threads': 10,
            'apscheduler.threadpool.core_threads': 10,
        }
        self.apsched = APScheduler(config)
        self.ctxt = context.get_admin_context()

        from gringotts.services import cinder
        from gringotts.services import glance
        from gringotts.services import neutron
        from gringotts.services import nova
        from gringotts.services import keystone
        from gringotts.services import ceilometer
        from gringotts.services import manila

        self.keystone_client = keystone

        self.RESOURCE_LIST_METHOD = [
            nova.server_list,
            glance.image_list,
            cinder.snapshot_list,
            cinder.volume_list,
            neutron.floatingip_list,
            neutron.router_list,
            neutron.network_list,
            neutron.port_list,
            neutron.listener_list,
            ceilometer.alarm_list,
            manila.share_list,
        ]

        self.RESOURCE_CREATE_MAP = {
            const.RESOURCE_FLOATINGIP: plugins.floatingip.FloatingIpCreateEnd(),
            const.RESOURCE_IMAGE: plugins.image.ImageCreateEnd(),
            const.RESOURCE_INSTANCE: plugins.instance.InstanceCreateEnd(),
            const.RESOURCE_ROUTER: plugins.router.RouterCreateEnd(),
            const.RESOURCE_LISTENER: plugins.listener.ListenerCreateEnd(),
            const.RESOURCE_SNAPSHOT: plugins.snapshot.SnapshotCreateEnd(),
            const.RESOURCE_VOLUME: plugins.volume.VolumeCreateEnd(),
            const.RESOURCE_ALARM: plugins.alarm.AlarmCreateEnd(),
            const.RESOURCE_USER: plugins.user.UserCreatedEnd(),
            const.RESOURCE_PROJECT: plugins.user.ProjectCreatedEnd(),
            const.RESOURCE_SHARE: plugins.share.ShareCreateEnd(),
        }

        self.RESOURCE_GET_MAP = {
            const.RESOURCE_INSTANCE: (nova.server_get, const.STATE_STOPPED),
            const.RESOURCE_SNAPSHOT: (cinder.snapshot_get, const.STATE_RUNNING),
            const.RESOURCE_VOLUME: (cinder.volume_get, const.STATE_RUNNING),
            const.RESOURCE_IMAGE: (glance.image_get, const.STATE_RUNNING),
            const.RESOURCE_FLOATINGIP: (neutron.floatingip_get, const.STATE_RUNNING),
            const.RESOURCE_ROUTER: (neutron.router_get, const.STATE_RUNNING),
            const.RESOURCE_LISTENER: (neutron.listener_get, const.STATE_RUNNING),
            const.RESOURCE_ALARM: (ceilometer.alarm_get, const.STATE_RUNNING),
            const.RESOURCE_SHARE: (manila.share_get, const.STATE_RUNNING),
        }

        self.DELETE_METHOD_MAP = {
            const.RESOURCE_INSTANCE: nova.delete_server,
            const.RESOURCE_IMAGE: glance.delete_image,
            const.RESOURCE_SNAPSHOT: cinder.delete_snapshot,
            const.RESOURCE_VOLUME: cinder.delete_volume,
            const.RESOURCE_FLOATINGIP: neutron.delete_fip,
            const.RESOURCE_ROUTER: neutron.delete_router,
            const.RESOURCE_LISTENER: neutron.delete_listener,
            const.RESOURCE_ALARM: ceilometer.delete_alarm,
            const.RESOURCE_SHARE: manila.delete_share,
        }

        self.STOP_METHOD_MAP = {
            const.RESOURCE_INSTANCE: nova.stop_server,
            const.RESOURCE_IMAGE: glance.stop_image,
            const.RESOURCE_SNAPSHOT: cinder.stop_snapshot,
            const.RESOURCE_VOLUME: cinder.stop_volume,
            const.RESOURCE_FLOATINGIP: neutron.stop_fip,
            const.RESOURCE_ROUTER: neutron.stop_router,
            const.RESOURCE_LISTENER: neutron.stop_listener,
            const.RESOURCE_ALARM: ceilometer.stop_alarm,
            const.RESOURCE_SHARE: manila.stop_share,
        }

        super(CheckerService, self).__init__(*args, **kwargs)

    def start(self):
        super(CheckerService, self).start()
        self.apsched.start()
        self.load_jobs()
        self.tg.add_timer(604800, lambda: None)

    def load_jobs(self):
        """Every check point is an apscheduler job that scheduled to different time
        with different period
        """
        non_center_jobs = [
            (self.check_if_resources_match_orders, 2, True),
            (self.check_if_owed_resources_match_owed_orders, 2, True),
            (self.check_if_cronjobs_match_orders, 1, True),
        ]

        center_jobs = [
            (self.check_owed_accounts_and_notify, 24, False),
            (self.check_user_to_account, 2, True),
            (self.check_project_to_project, 2, True),
        ]

        if cfg.CONF.checker.enable_non_center_jobs:
            for job, period, right_now in non_center_jobs:
                if right_now:
                    job()
                self.apsched.add_interval_job(job, hours=period)

        if cfg.CONF.checker.enable_center_jobs:
            for job, period, right_now in center_jobs:
                if right_now:
                    job()
                start_date = utils.utc_to_local(self._absolute_9_clock())
                self.apsched.add_interval_job(job,
                                              hours=period,
                                              start_date=start_date)

    def _absolute_9_clock(self):
        nowutc = datetime.datetime.utcnow()
        nowutc_time = nowutc.time()
        nowutc_date = nowutc.date()
        clock = datetime.time(1, 0, 0)
        if nowutc_time > clock:
            nowutc_date = nowutc_date + datetime.timedelta(hours=24)
        return datetime.datetime.combine(nowutc_date, clock)

    def _check_resource_to_order(self, resource, resource_to_order, bad_resources, try_to_fix):
        LOG.debug('Checking resource: %s' % resource.as_dict())

        try:
            order = resource_to_order[resource.id]
        except KeyError:
            # Situation 1: There may exist resources that have no orders
            if resource.status == const.STATE_ERROR:
                bad_resources.append(resource)
                return
            if not resource.is_bill:
                return
            try_to_fix['1'].append(resource)
        else:
            # Situation 2: There may exist resource whose status doesn't match with its order's
            if resource.status == const.STATE_ERROR:
                bad_resources.append(resource)
            elif hasattr(resource, 'admin_state') and resource.admin_state != order['status']:
                ## for loadbalancer listener
                action_time = utils.format_datetime(timeutils.strtime())
                try_to_fix['2'].append(Situation2Item(order['order_id'],
                                                      action_time,
                                                      resource.admin_state,
                                                      resource.project_id))
            elif not hasattr(resource, 'admin_state') and resource.status != order['status']:
                action_time = utils.format_datetime(timeutils.strtime())
                try_to_fix['2'].append(Situation2Item(order['order_id'],
                                                      action_time,
                                                      resource.status,
                                                      resource.project_id))
            # Situation 3: Resource's order has been created,
            # but its bill not be created by master
            elif not order['cron_time'] and order['status'] != const.STATE_STOPPED:
                try_to_fix['3'].append(Situation3Item(order['order_id'],
                                                      resource.created_at,
                                                      resource.project_id))
            # Situation 5: The order's unit_price is different from the
            # resource's actual price
            else:
                unit_price = self.RESOURCE_CREATE_MAP[resource.resource_type].\
                        get_unit_price(resource.to_message(),
                                       resource.admin_state if hasattr(resource, 'admin_state') else resource.status,
                                       cron_time=order['cron_time'])
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

    def _check_if_resources_match_orders(self, bad_resources, try_to_fix):
        """Check one time to collect orders/resources that may need to fix and notify
        """
        projects = self.keystone_client.get_project_list()
        for project in projects:
            if project.id in cfg.CONF.checker.ignore_tenants:
                continue
            # Get all active orders
            resource_to_order = {}
            orders = self.worker_api.get_active_orders(self.ctxt,
                                                       region_id=self.region_name,
                                                       project_id=project.id)
            for order in orders:
                if not isinstance(order, dict):
                    order = order.as_dict()
                order['checked'] = False
                resource_to_order[order['resource_id']] = order

            # Check resource to order
            for method in self.RESOURCE_LIST_METHOD:
                resources = method(project.id, region_name=self.region_name, project_name=project.name)
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

    def check_if_resources_match_orders(self):
        """There are 3 situations in every check:

        * There exist resources that are not billed
        * There exist resources whose status don't match with its order's status
        * There exist active orders that their resource has been deleted

        We do this check every one hour.
        """
        LOG.warn('Checking if resources match with orders')
        bad_resources_1 = []
        bad_resources_2 = []
        try_to_fix_1 = {'1': [], '2': [], '3': [], '4': [], '5': []}
        try_to_fix_2 = {'1': [], '2': [], '3': [], '4': [], '5': []}
        try:
            self._check_if_resources_match_orders(bad_resources_1, try_to_fix_1)
            time.sleep(30)
            self._check_if_resources_match_orders(bad_resources_2, try_to_fix_2)
        except Exception:
            LOG.exception('Some exceptions occurred when checking whether '
                          'resources match with orders or not.')
        finally:
            # Alert bad resources
            bad_resources = [x for x in bad_resources_2 if x in bad_resources_1]
            if bad_resources:
                alert.alert_bad_resources(bad_resources)

            # Fix bad resources and orders
            try_to_fix_situ_1 = [x for x in try_to_fix_2['1'] if x in try_to_fix_1['1']]
            try_to_fix_situ_2 = [x for x in try_to_fix_2['2'] if x in try_to_fix_1['2']]
            try_to_fix_situ_3 = [x for x in try_to_fix_2['3'] if x in try_to_fix_1['3']]
            try_to_fix_situ_4 = [x for x in try_to_fix_2['4'] if x in try_to_fix_1['4']]
            try_to_fix_situ_5 = [x for x in try_to_fix_2['5'] if x in try_to_fix_1['5']]

            ## Situation 1
            for resource in try_to_fix_situ_1:
                LOG.warn('Situation 1: In project(%s), the resource(%s) has no order' % \
                        (resource.project_id, resource.id))
                if cfg.CONF.checker.try_to_fix:
                    create_cls = self.RESOURCE_CREATE_MAP[resource.resource_type]
                    create_cls.process_notification(resource.to_message(),
                                                    resource.status)
            ## Situation 2
            for item in try_to_fix_situ_2:
                LOG.warn('Situation 2: In project(%s), the order(%s) and its resource\'s status doesn\'t match' % \
                        (item.project_id, item.order_id))
                if cfg.CONF.checker.try_to_fix:
                    self.master_api.resource_changed(self.ctxt,
                                                     item.order_id,
                                                     item.action_time,
                                                     change_to=item.change_to,
                                                     remarks="System Adjust")
            ## Situation 3
            for item in try_to_fix_situ_3:
                LOG.warn('Situation 3: In project(%s), the order(%s) has no bills' % \
                        (item.project_id, item.order_id))
                if cfg.CONF.checker.try_to_fix:
                    self.master_api.resource_created_again(self.ctxt,
                                                           item.order_id,
                                                           item.resource_created_at,
                                                           "Sytstem Adjust")
            ## Situation 4
            for item in try_to_fix_situ_4:
                LOG.warn('Situation 4: In project(%s), the order(%s)\'s resource has been deleted.' % \
                        (item.project_id, item.order_id))
                if cfg.CONF.checker.try_to_fix:
                    self.master_api.resource_deleted(self.ctxt,
                                                     item.order_id,
                                                     item.deleted_at,
                                                     "Resource Has Been Deleted")
            ## Situation 5
            for item in try_to_fix_situ_5:
                LOG.warn('Situation 5: In project(%s), the order(%s)\'s unit_price is wrong, should be %s' % \
                        (item.project_id, item.order_id, item.unit_price))
                if cfg.CONF.checker.try_to_fix:
                    create_cls = self.RESOURCE_CREATE_MAP[item.resource.resource_type]
                    create_cls.change_unit_price(item.resource.to_message(),
                                                 item.resource.status,
                                                 item.order_id)

    def _check_if_owed_resources_match_owed_orders(self,
                                                   should_stop_resources,
                                                   should_delete_resources):
        projects = self.keystone_client.get_project_list()
        for project in projects:
            orders = list(self.worker_api.get_active_orders(self.ctxt,
                                                            region_id=self.region_name,
                                                            project_id=project.id,
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
                resource = self.RESOURCE_GET_MAP[order['type']][0](order['resource_id'],
                                                                   region_name=self.region_name)
                now = datetime.datetime.utcnow()
                if order['date_time'] < now:
                    if resource:
                        should_delete_resources.append(resource)
                else:
                    if not resource:
                        LOG.warn('The resource of the order(%s) not exists' % order)
                        continue
                    if order['type'] == const.RESOURCE_FLOATINGIP and not resource.is_reserved and order['owed']:
                        should_delete_resources.append(resource)
                    elif resource.status != self.RESOURCE_GET_MAP[order['type']][1]:
                        should_stop_resources.append(resource)

    def check_if_owed_resources_match_owed_orders(self):
        LOG.warn('Checking if owed resources match with owed orders')
        should_stop_resources_1 = []
        should_stop_resources_2 = []
        should_delete_resources_1 = []
        should_delete_resources_2 = []
        try:
            self._check_if_owed_resources_match_owed_orders(should_stop_resources_1,
                                                            should_delete_resources_1)
            time.sleep(30)
            self._check_if_owed_resources_match_owed_orders(should_stop_resources_2,
                                                            should_delete_resources_2)
        except Exception:
            LOG.exception('Some exceptions occurred when checking whether '
                          'owed resources match with owed orders or not.')
        finally:
            should_stop_resources = [x for x in should_stop_resources_2 if x in should_stop_resources_1]
            should_delete_resources = [x for x in should_delete_resources_2 if x in should_delete_resources_1]
            for resource in should_stop_resources:
                LOG.warn("The resource(%s) is owed, should be stopped" % resource)
                if cfg.CONF.checker.try_to_fix:
                    self.STOP_METHOD_MAP[resource.resource_type](resource.id, self.region_name)
            for resource in should_delete_resources:
                LOG.warn("The resource(%s) is reserved for its full days, should be deleted" % resource)
                if cfg.CONF.checker.try_to_fix:
                    self.DELETE_METHOD_MAP[resource.resource_type](resource.id, self.region_name)

    def check_if_cronjobs_match_orders(self):
        """Check if number of cron jobs match number of orders in running and
        stopped state, we do this check every one hour.
        """
        LOG.warn('Checking if cronjobs match with orders')
        try:
            order_count = self.worker_api.get_active_order_count(self.ctxt, self.region_name)
            cronjob_count = self.master_api.get_cronjob_count(self.ctxt)
            if cronjob_count != order_count:
                LOG.warn('There are %s cron jobs, but there are %s active orders' %
                         (cronjob_count, order_count))
            else:
                LOG.warn('Checked, There are %s cron jobs, and %s active orders' %
                          (cronjob_count, order_count))

            # Checking owed orders
            datejob_count = self.master_api.get_datejob_count(self.ctxt)
            owed_order_count = self.worker_api.get_active_order_count(
                self.ctxt, self.region_name, owed=True)
            if datejob_count != owed_order_count:
                LOG.warn('There are %s date jobs, but there are %s owed active orders' %
                         (datejob_count, owed_order_count))
            else:
                LOG.warn('Checked, There are %s date jobs, and %s owed active orders' %
                         (datejob_count, owed_order_count))

            # checking 30 days orders
            datejob_30_days_count = self.master_api.get_datejob_count_30_days(self.ctxt)
            stopped_order_count = self.worker_api.get_stopped_order_count(
                self.ctxt, self.region_name, type=const.RESOURCE_INSTANCE)
            LOG.warn('Checked, There are %s 30-days date jobs, and %s stopped orders' %
                     (datejob_30_days_count, stopped_order_count))
        except Exception:
            LOG.exception('Some exceptions occurred when checking whether '
                          'cron jobs match with orders or not')

    def check_owed_accounts_and_notify(self):
        LOG.warn('Notifying owed accounts')
        try:
            accounts = list(self.worker_api.get_accounts(self.ctxt))
        except Exception:
            LOG.exception("Fail to get all accounts")
            accounts = []
        for account in accounts:
            try:
                if account['level'] == 9:
                    continue

                if not isinstance(account, dict):
                    account = account.as_dict()

                if account['owed']:
                    orders = list(
                        self.worker_api.get_active_orders(self.ctxt,
                                                          user_id=account['user_id'],
                                                          owed=True)
                    )
                    if not orders:
                        continue

                    contact = self.keystone_client.get_uos_user(account['user_id'])
                    _projects = self.worker_api.get_projects(self.ctxt, user_id=account['user_id'], type='simple')

                    orders_dict = {}
                    for project in _projects:
                        orders_dict[project['project_id']] = []

                    for order in orders:
                        # check if the resource exists
                        resource = self.RESOURCE_GET_MAP[order['type']][0](order['resource_id'],
                                                                           region_name=order['region_id'])
                        if not resource:
                            # alert that the resource not exists
                            LOG.warn("The resource(%s|%s) may has been deleted" % \
                                     (order['type'], order['resource_id']))
                            alert.wrong_billing_order(order, 'resource_deleted')
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
                            LOG.warn('The order %s reserved_days is less than 0' % order['order_id'])
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
                            adict['orders'] = orders_dict[project['project_id']]
                            projects.append(adict)

                    if not projects:
                        continue

                    reserved_days = utils.cal_reserved_days(account['level'])
                    account['reserved_days'] = reserved_days
                    country_code = contact.get("country_code") or "86"
                    language = "en_US" if country_code != '86' else "zh_CN"
                    self.notifier.notify_has_owed(self.ctxt, account, contact, projects, language=language)
                else:
                    orders = self.worker_api.get_active_orders(self.ctxt,
                                                               user_id=account['user_id'])
                    if not orders:
                        continue

                    _projects = self.worker_api.get_projects(self.ctxt, user_id=account['user_id'], type='simple')

                    estimation = {}
                    for project in _projects:
                        estimation[project['project_id']] = 0

                    price_per_hour = 0
                    for order in orders:
                        # check if the resource exists
                        resource = self.RESOURCE_GET_MAP[order['type']][0](order['resource_id'],
                                                                           region_name=order['region_id'])
                        if not resource:
                            # alert that the resource not exists
                            LOG.warn("The resource(%s|%s) may has been deleted" % \
                                     (order['type'], order['resource_id']))
                            alert.wrong_billing_order(order, 'resource_deleted')
                            continue

                        price_per_hour += utils._quantize_decimal(order['unit_price'])
                        estimation[order['project_id']] += utils._quantize_decimal(order['unit_price'])

                    price_per_day = price_per_hour * 24
                    account_balance = utils._quantize_decimal(account['balance'])

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
                        adict['estimation'] = str(estimation[project['project_id']] * 24)
                        projects.append(adict)

                    if not projects:
                        continue

                    contact = self.keystone_client.get_uos_user(account['user_id'])
                    country_code = contact.get("country_code") or "86"
                    language = "en_US" if country_code != '86' else "zh_CN"
                    self.notifier.notify_before_owed(self.ctxt, account, contact, projects,
                                                     str(price_per_day), days_to_owe,
                                                     language=language)
            except Exception:
                LOG.exception('Some exceptions occurred when checking owed account: %s' % account['user_id'])

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
                if getattr(a, akey) < b.get(bkey) or i == l-1:
                    s = i
                    ab.append(a)
                    break
        return ab

    def _check_user_to_account(self):
        LOG.warn("Checking if users in keystone match accounts in gringotts")
        accounts = sorted(self.worker_api.get_accounts(self.ctxt), key=lambda account: account['user_id'])
        users = sorted(self.keystone_client.get_user_list(), key=lambda user: user.id)

        _users = self._figure_out_difference(users, 'id', accounts, 'user_id')
        result = []
        for u in _users:
            result.append(User(u.id, u.domain_id,
                               project_id=getattr(u, 'default_project_id', None)))
        return result

    def check_user_to_account(self):
        try:
            users_1 = self._check_user_to_account()
            time.sleep(30)
            users_2 = self._check_user_to_account()
        except Exception:
            users_1 = users_2 = []
            LOG.exception('Some exceptions occurred when checking whether '
                          'users match with account.')
        finally:
            users = [u for u in users_1 if u in users_2]
            for user in users:
                LOG.warn('Situation 6: The user(%s) has not been created in gringotts' % user.user_id)
                if cfg.CONF.checker.try_to_fix:
                    create_cls = self.RESOURCE_CREATE_MAP[const.RESOURCE_USER]
                    create_cls.process_notification(user.to_message())

    def _check_project_to_project(self):
        LOG.warn("Checking if projects in keystone match projects in gringotts")
        _k_projects = self.keystone_client.get_projects_by_project_ids()
        _g_projects = self.worker_api.get_projects(self.ctxt, type='simple')

        k_projects = []
        g_projects = []
        for kp in _k_projects:
            billing_owner = kp['users']['billing_owner']
            k_projects.append(Project(kp['id'],
                                      billing_owner.get('id') if billing_owner else None,
                                      kp['domain_id']))
        for gp in _g_projects:
            g_projects.append(Project(gp['project_id'],
                                      gp['billing_owner'],
                                      gp['domain_id']))

        # projects in keystone but not in gringotts
        creating_projects = list(set(k_projects) - set(g_projects))

        # projects in gringotts but not in keystone
        deleting_projects = []
        _deleted_projects = list(set(g_projects) - set(k_projects))
        for p in _deleted_projects:
            if self.worker_api.get_resources(self.ctxt, p.project_id):
                deleting_projects.append(p)

        # projects whose billing owner is not equal to each other
        billing_projects = [] # changing billing owner
        projects_k = sorted(set(g_projects) & set(k_projects), key=lambda p: p.project_id)
        projects_g = sorted(set(k_projects) & set(g_projects), key=lambda p: p.project_id)

        for k, g in zip(projects_k, projects_g):
            if k.billing_owner_id != g.billing_owner_id:
                billing_projects.append(k)

        return (creating_projects, deleting_projects, billing_projects)

    def check_project_to_project(self):
        """Check two situations:
        1. Projects in keystone but not in gringotts, means gringotts didn't receive the create
           project message.
        2. Projects in gringotts but not in keystone still has resources, means projects in keystone
           has been deleted, but its resources didn't be deleted
        3. Check the project's billing owner in gringotts matches billing owner in keystone
        """
        try:
            cp_1, dp_1, bp_1 = self._check_project_to_project()
            time.sleep(30)
            cp_2, dp_2, bp_2 = self._check_project_to_project()
        except Exception:
            cp_1 = dp_1 = bp_1 = []
            cp_2 = dp_2 = bp_2 = []
            LOG.exception('Some exceptions occurred when checking whether '
                          'projects match with projects.')
        finally:
            creating_projects = [p for p in cp_1 if p in cp_2]
            deleting_projects = [p for p in dp_1 if p in dp_2]
            billing_projects = [p for p in bp_1 if p in bp_2]

            for p in creating_projects:
                LOG.warn("Situation 7: The project(%s) exists in keystone but not in gringotts, its billing owner is %s" % \
                        (p.project_id, p.billing_owner_id))
                if cfg.CONF.checker.try_to_fix and p.billing_owner_id:
                    create_cls = self.RESOURCE_CREATE_MAP[const.RESOURCE_PROJECT]
                    create_cls.process_notification(p.to_message())

            for p in deleting_projects:
                LOG.warn("Situation 8: The project(%s) has been deleted, but its resources has not been cleared" % p.project_id)
                if cfg.CONF.checker.try_to_fix:
                    try:
                        self.worker_api.delete_resources(self.ctxt, p.project_id)
                    except Exception:
                        LOG.exception('Fail to delete all resources of project %s' % p.project_id)
                        return
                    LOG.info('Delete all resources of project %s successfully' % p.project_id)

            for p in billing_projects:
                LOG.warn("Situation 9: The project(%s)\'s billing owner in gringotts is not equal to keystone\'s, should be: %s" % \
                        (p.project_id, p.billing_owner_id))
                if cfg.CONF.checker.try_to_fix and p.billing_owner_id:
                    try:
                        self.worker_api.change_billing_owner(self.ctxt, p.project_id, p.billing_owner_id)
                    except Exception:
                        LOG.exception('Fail to change billing owner of project %s to user %s' % (p.project_id, p.billing_owner_id))
                        return
                    LOG.info('Change billing owner of project %s to user %s successfully' % (p.project_id, p.billing_owner_id))


def checker():
    prepare_service()
    os_service.launch(CheckerService()).wait()
