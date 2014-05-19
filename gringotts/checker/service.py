import datetime
from oslo.config import cfg

from apscheduler.scheduler import Scheduler as APScheduler

from gringotts import master
from gringotts import worker
from gringotts import exception
from gringotts import context
from gringotts import utils
from gringotts import constants as const
from gringotts.service import prepare_service

from gringotts.waiter import plugins

from gringotts.openstack.common import log
from gringotts.openstack.common import timeutils
from gringotts.openstack.common import service as os_service


LOG = log.getLogger(__name__)
TIMESTAMP_TIME_FORMAT = '%Y-%m-%d %H:%M:%S.%f'


OPTS = [
    cfg.BoolOpt('try_to_fix',
                default=False,
                help='If found some exceptio, we try to fix it or not'),
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
        interval_jobs = [(self.check_if_resources_match_orders, 1),
                         (self.check_if_cronjobs_match_orders, 1),
                         (self.check_if_account_match_role, 24),
                         (self.check_if_consumptions_match_total_price, 24)]

        for job, period in interval_jobs:
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
            LOG.exception('Some exceptions occurred when checking whether'
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
            LOG.exception('Some exceptions occurred when checking whether'
                          'cron jobs match with orders or not')

    def _has_owner_role(self, roles):
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

                if account['owed'] and not self._has_owner_role(roles):
                    LOG.warn('Account(%s) owed, but has no owner role' %
                             account['project_id'])
                    if cfg.CONF.try_to_fix:
                        self.keystone_client.grant_owed_role(account['user_id'],
                                                             account['project_id'])
                elif not account['owed'] and self._has_owner_role(roles):
                    LOG.warn('Account(%s) not owed, but has owner role' %
                             account['project_id'])
                    if cfg.CONF.try_to_fix:
                        self.keystone_client.revoke_owed_role(account['user_id'],
                                                              account['project_id'])
        except Exception:
            LOG.exception('Some exceptions occurred when checking whether'
                          'accounts match with their roles or not')

    def check_if_consumptions_match_total_price(self):
        """Check if consumption of an account match sum of all orders' total_price
        """
        LOG.warn('Checking if consumptions match with total price')
        try:
            pass
        except Exception:
            LOG.exception('Some exceptions occurred when checking whether'
                          'consumptions match with total price or not')


def checker():
    prepare_service()
    os_service.launch(CheckerService()).wait()
