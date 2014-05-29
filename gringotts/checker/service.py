import datetime
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
                help='Enable the interval jobs that run in non center regions')
]

cfg.CONF.register_opts(OPTS, group="checker")


def _utc_to_local(utc_dt):
    from_zone = tz.tzutc()
    to_zone = tz.tzlocal()
    return utc_dt.replace(tzinfo=from_zone).astimezone(to_zone).replace(tzinfo=None)


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

        self.keystone_client = keystone

        self.RESOURCE_LIST_METHOD = [
            nova.server_list,
            glance.image_list,
            cinder.snapshot_list,
            cinder.volume_list,
            neutron.floatingip_list,
            neutron.router_list,
        ]

        self.RESOURCE_CREATE_MAP = {
            const.RESOURCE_FLOATINGIP: plugins.floatingip.FloatingIpCreateEnd(),
            const.RESOURCE_IMAGE: plugins.image.ImageCreateEnd(),
            const.RESOURCE_INSTANCE: plugins.instance.InstanceCreateEnd(),
            const.RESOURCE_ROUTER: plugins.router.RouterCreateEnd(),
            const.RESOURCE_SNAPSHOT: plugins.snapshot.SnapshotCreateEnd(),
            const.RESOURCE_VOLUME: plugins.volume.VolumeCreateEnd()
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
            (self.check_if_resources_match_orders, 1, True),
            (self.check_if_cronjobs_match_orders, 1, True),
        ]

        center_jobs = [
            (self.check_if_account_match_role, 24, True),
            (self.check_if_consumptions_match_total_price, 24, True),
            (self.check_if_order_over_billed, 24, True),
            (self.check_owed_accounts_and_notify, 24, False),
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
                self.apsched.add_interval_job(job, hours=period)

    def _check_resource_to_order(self, resource, resource_to_order):
        LOG.debug('Checking resource: %s' % resource.as_dict())

        try:
            order = resource_to_order[resource.id]
        except KeyError:
            # Situation 1: There exist resources that are not billed
            # TODO(suo): Create order and bills for these resources
            LOG.warn('The resource(%s) has no order' % resource.as_dict())

            if resource.status == const.STATE_ERROR:
                LOG.warn('The status of the resource(%s) is not steady or in error.' %
                         resource.as_dict())
                return
            if cfg.CONF.checker.try_to_fix:
                now = datetime.datetime.utcnow()
                created = timeutils.parse_strtime(resource.created_at,
                                                  fmt=TIMESTAMP_TIME_FORMAT)
                if timeutils.delta_seconds(created, now) > 300:
                    create_cls = self.RESOURCE_CREATE_MAP[resource.resource_type]
                    create_cls.process_notification(resource.to_message(),
                                                    resource.status)
        else:
            # Situation 2: There exist resources whose status don't match with its order's status
            # TODO(suo): Change order for these resources
            if resource.status == const.STATE_ERROR:
                LOG.warn('The status of the resource(%s) is not steady or in error.' %
                         resource.as_dict())
            elif resource.status != order['status']:
                LOG.warn('The status of the resource(%s) doesn\'t match with the status of the order(%s)' %
                         (resource.as_dict(), order))

                if cfg.CONF.checker.try_to_fix:
                    action_time = utils.format_datetime(timeutils.strtime())
                    self.master_api.resource_changed(self.ctxt,
                                                     order['order_id'],
                                                     action_time,
                                                     change_to=resource.status,
                                                     remarks="System Adjust")
            # Order has created, but its bill not be created by master
            elif not order['cron_time']:
                LOG.warn('The order(%s) has been created, its bill not yet' % order)

                if cfg.CONF.checker.try_to_fix:
                    self.master_api.resource_created_again(self.ctxt,
                                                           order['order_id'],
                                                           resource.created_at,
                                                           "Sytstem Adjust")

            resource_to_order[resource.id]['checked'] = True

    def _check_order_to_resource(self, resource_id, order):
        LOG.warn('The resource of the order(%s) has been deleted.' % order)
        if cfg.CONF.checker.try_to_fix:
            deleted_at = utils.format_datetime(timeutils.strtime())
            self.master_api.resource_deleted(self.ctxt, order['order_id'],
                                             deleted_at)

    def check_if_resources_match_orders(self):
        """There are 3 situations in every check:

        * There exist resources that are not billed
        * There exist resources whose status don't match with its order's status
        * There exist active orders that their resource has been deleted

        We do this check every one hour.
        """
        LOG.warn('Checking if resources match with orders')
        try:
            projects = self.keystone_client.get_project_list()
            for project in projects:
                # Get all active orders
                states = [const.STATE_RUNNING, const.STATE_STOPPED, const.STATE_SUSPEND,
                          const.STATE_CHANGING]
                resource_to_order = {}
                for s in states:
                    orders = self.worker_api.get_orders(self.ctxt,
                                                        status=s,
                                                        region_id=self.region_name,
                                                        project_id=project.id)
                    for order in orders:
                        if not isinstance(order, dict):
                            order = order.as_dict()
                        order['checked'] = False
                        resource_to_order[order['resource_id']] = order

                # Check resource to order
                for method in self.RESOURCE_LIST_METHOD:
                    resources = method(project.id, region_name=self.region_name)
                    for resource in resources:
                        self._check_resource_to_order(resource,
                                                      resource_to_order)
                # Check order to resource
                for resource_id, order in resource_to_order.items():
                    if order['checked']:
                        continue
                    # Situation 3: There exist active orders that their resource has been deleted
                    # TODO(suo): Close bills for these deleted resources
                    self._check_order_to_resource(resource_id, order)
        except Exception:
            LOG.exception('Some exceptions occurred when checking whether '
                          'resources match with orders or not')

    def check_if_cronjobs_match_orders(self):
        """Check if number of cron jobs match number of orders in running and
        stopped state, we do this check every one hour.
        """
        LOG.warn('Checking if cronjobs match with orders')
        try:
            # Checking active orders
            cronjob_count = self.master_api.get_cronjob_count(self.ctxt)
            # active means including running, stopped, changing, suspend
            order_count = self.worker_api.get_active_order_count(
                self.ctxt, self.region_name)
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
        except Exception:
            LOG.exception('Some exceptions occurred when checking whether '
                          'cron jobs match with orders or not')

    def _has_ower_role(self, roles):
        for role in roles:
            if role.name == 'ower':
                return True
        return False

    def check_if_account_match_role(self):
        """Check if accounts match with their roles
        """
        LOG.warn('Checking if accounts match with their roles')
        try:
            accounts = list(self.worker_api.get_accounts(self.ctxt))
            projects = self.keystone_client.get_project_list()

            c_accounts = len(accounts)
            c_projects = len(projects)

            if c_accounts != c_projects:
                LOG.warn('The count(%s) of accounts is not equal to the count(%s) '
                         'of projects' % (c_accounts, c_projects))

            for account in accounts:
                roles = self.keystone_client.get_role_list(
                    user=account['user_id'],
                    project=account['project_id'])

                if account['owed'] and not self._has_ower_role(roles):
                    LOG.warn('Account(%s) owed, but has no ower role' %
                             account['project_id'])
                    if cfg.CONF.checker.try_to_fix:
                        self.keystone_client.grant_owed_role(account['user_id'],
                                                             account['project_id'])
                elif not account['owed'] and self._has_ower_role(roles):
                    LOG.warn('Account(%s) not owed, but has ower role' %
                             account['project_id'])
                    if cfg.CONF.checker.try_to_fix:
                        self.keystone_client.revoke_owed_role(account['user_id'],
                                                              account['project_id'])
        except Exception:
            LOG.exception('Some exceptions occurred when checking whether '
                          'accounts match with their roles or not')

    def check_owed_accounts_and_notify(self):
        LOG.warn('Notify owed accounts')
        try:
            accounts = list(self.worker_api.get_accounts(self.ctxt))
            for account in accounts:
                if account['level'] == 9:
                    continue

                if not isinstance(account, dict):
                    account = account.as_dict()

                if account['owed']:
                    orders = list(
                        self.worker_api.get_active_orders(self.ctxt,
                                                          project_id=account['project_id'],
                                                          owed=True)
                    )
                    if not orders:
                        continue

                    contact = self.keystone_client.get_uos_user(account['user_id'])

                    orders_dict = []

                    for order in orders:
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
                        reserved_days = order['date_time'].day - now.day
                        order_d['reserved_days'] = reserved_days

                        order_d['date_time'] = timeutils.strtime(
                                order['date_time'],
                                fmt=ISO8601_UTC_TIME_FORMAT)

                        orders_dict.append(order_d)

                    reserved_days = utils.cal_reserved_days(account['level'])
                    account['reserved_days'] = reserved_days
                    self.notifier.notify_has_owed(self.ctxt, account, contact, orders_dict)
                else:
                    orders = self.worker_api.get_active_orders(self.ctxt,
                                                               project_id=account['project_id'])
                    if not orders:
                        continue

                    price_per_hour = 0
                    for order in orders:
                        price_per_hour += utils._quantize_decimal(order['unit_price'])

                    price_per_day = price_per_hour * 24
                    account_balance = utils._quantize_decimal(account['balance'])

                    if price_per_day == 0:
                        continue

                    days_to_owe = int(account_balance / price_per_day)
                    if days_to_owe > cfg.CONF.checker.days_to_owe:
                        continue

                    contact = self.keystone_client.get_uos_user(account['user_id'])
                    self.notifier.notify_before_owed(self.ctxt, account, contact,
                                                     str(price_per_day), days_to_owe)
        except Exception:
            LOG.exception('Some exceptions occurred when checking owed accounts')

    def check_if_order_over_billed(self):
        LOG.warn('Checking if orders are over billed')
        try:
            orders = self.worker_api.get_active_orders(self.ctxt)
            for order in orders:
                if not isinstance(order, dict):
                    order = order.as_dict()
                if isinstance(order['cron_time'], basestring):
                    order['cron_time'] = timeutils.parse_strtime(
                            order['cron_time'],
                            fmt=ISO8601_UTC_TIME_FORMAT)
                one_hour_later= timeutils.utcnow() + datetime.timedelta(hours=1)
                if order['cron_time'] > one_hour_later:
                    LOG.warn('The order(%s) is over billed' % order)
                    if cfg.CONF.checker.try_to_fix:
                        self.worker_api.fix_order(self.ctxt, order['order_id'])
        except Exception:
            LOG.exception('Some exceptions occurred when checking whether orders are over billed')

    def check_if_consumptions_match_total_price(self):
        """Check if consumption of an account match sum of all orders' total_price
        """
        LOG.warn('Checking if consumptions match with total price')
        try:
            pass
        except Exception:
            LOG.exception('Some exceptions occurred when checking whether '
                          'consumptions match with total price or not')


def checker():
    prepare_service()
    os_service.launch(CheckerService()).wait()
