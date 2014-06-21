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
from gringotts.services import alert

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
                help="A list of tenant that should not to check")
]

cfg.CONF.register_opts(OPTS, group="checker")


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
            neutron.network_list,
            neutron.port_list
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

    def _check_resource_to_order(self, resource, resource_to_order, bad_resources):
        LOG.debug('Checking resource: %s' % resource.as_dict())

        try:
            order = resource_to_order[resource.id]
        except KeyError:
            # Situation 1: There exist resources that are not billed
            # TODO(suo): Create order and bills for these resources
            if resource.is_bill:
                LOG.warn('The resource(%s) has no order' % resource.as_dict())

            if resource.status == const.STATE_ERROR:
                LOG.warn('The status of the resource(%s) is not steady or in error.' %
                         resource.as_dict())
                bad_resources.append(resource)
                return

            if not resource.is_bill:
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
                bad_resources.append(resource)
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
        bad_resources = []
        try:
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
                                                      bad_resources)
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
        finally:
            if bad_resources:
                alert.alert_bad_resources(bad_resources)

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

    def check_owed_accounts_and_notify(self):
        LOG.warn('Notifying owed accounts')
        try:
            accounts = list(self.worker_api.get_accounts(self.ctxt))
            projects = self.keystone_client.get_project_list()

            # Check if number of account is equal to number of projects
            c_accounts = len(accounts)
            c_projects = len(projects)

            if c_accounts != c_projects:
                LOG.warn('The count(%s) of accounts is not equal to the count(%s) '
                         'of projects' % (c_accounts, c_projects))

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


def checker():
    prepare_service()
    os_service.launch(CheckerService()).wait()
