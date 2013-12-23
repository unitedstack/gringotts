from oslo.config import cfg

from apscheduler.scheduler import Scheduler as APScheduler
from datetime import timedelta

from gringotts import db
from gringotts import worker

from gringotts.openstack.common import log
from gringotts.openstack.common.rpc import service as rpc_service
from gringotts.openstack.common import service as os_service
from gringotts.service import prepare_service


LOG = log.getLogger(__name__)

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
        self.worker_api = worker.API()
        self.apsched = APScheduler()
        self.db_conn = db.get_connection(cfg.CONF)
        self.jobs = {}
        super(MasterService, self).__init__(*args, **kwargs)

    def start(self):
        super(MasterService, self).start()
        self.apsched.start()
        # Add a dummy thread to have wait() working
        self.tg.add_timer(604800, lambda: None)

    def _pre_deduct(self, subscription):
        self.worker_api.pre_deduct(subscription)

    def _create_cron_job(self, subscription, action_time):
        """For now, we only supprot hourly cron job
        """
        job = self.apsched.add_interval_job(MasterService._pre_deduct,
                                            hours=1,
                                            start_date=action_time + timedelta(hours=1),
                                            args=[subscription])
        self.jobs[subscription.subscription_id] = job

    def _delete_cron_job(self, subscription_id):
        """Delete cron job related to this subscription
        """
        # FIXME(suo): Actually, we should store job to DB layer, not
        # in memory
        job = self.jobs.get(subscription_id)
        self.apsched.unschedule_job(job)

    def resource_created(self, ctxt, subscriptions, action_time, remarks):
        LOG.debug('Resource created')
        for sub in subscriptions:
            self.worker_api.create_bill(sub, action_time, remarks)
            self._create_cron_job(sub, action_time)

    def resource_deleted(self, ctxt, subscriptions, action_time):
        LOG.debug('Instance deleted')
        for sub in subscriptions:
            self.worker_api.back_deduct(sub, action_time)
            self._delete_cron_job(sub.subscription_id)

    def resource_changed(self, ctxt, subscriptions, action_time, remarks):
        for sub in subscriptions:
            if sub.status == 'active':
                self.worker_api.back_deduct(sub, action_time)
                self._delete_cron_job(sub.subscription_id)
            elif sub.status == 'inactive':
                self.worker_api.create_bill(sub, action_time, remarks)
                self._create_cron_job(sub, action_time)


def master():
    prepare_service()
    os_service.launch(MasterService()).wait()
