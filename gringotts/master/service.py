from oslo.config import cfg

from apscheduler.scheduler import Scheduler as APScheduler
from datetime import timedelta

from gringotts import db
from gringotts import worker

from gringotts.openstack.common import context
from gringotts.openstack.common import log
from gringotts.openstack.common.rpc import service as rpc_service
from gringotts.openstack.common import service as os_service
from gringotts.openstack.common import timeutils
from gringotts.service import prepare_service


LOG = log.getLogger(__name__)

TIMESTAMP_TIME_FORMAT = '%Y-%m-%d %H:%M:%S.%f'

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

    def _pre_deduct(self, subscription_id):
        self.worker_api.pre_deduct(context.RequestContext(), subscription_id)

    def _create_cron_job(self, subscription_id, action_time):
        """For now, we only supprot hourly cron job
        """
        action_time = timeutils.parse_strtime(action_time,
                                              fmt=TIMESTAMP_TIME_FORMAT)
        job = self.apsched.add_interval_job(self._pre_deduct,
                                            #hours=1,
                                            minutes=1,
                                            start_date=action_time + timedelta(minutes=1),
                                            #start_date=action_time + timedelta(hours=1),
                                            args=[subscription_id])
        self.jobs[subscription_id] = job

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
            self.worker_api.create_bill(context.RequestContext(),
                                        sub, action_time, remarks)
            self._create_cron_job(sub.get('subscription_id'), action_time)

    def resource_deleted(self, ctxt, subscriptions, action_time):
        LOG.debug('Instance deleted')
        for sub in subscriptions:
            self.worker_api.close_bill(context.RequestContext(),
                                       sub, action_time)
            self._delete_cron_job(sub.get('subscription_id'))

    def resource_changed(self, ctxt, subscriptions, action_time, remarks):
        for sub in subscriptions:
            if sub.status == 'active':
                self.worker_api.close_bill(context.RequestContext(),
                                           sub, action_time)
                self._delete_cron_job(sub.get('subscription_id'))
            elif sub.status == 'inactive':
                self.worker_api.create_bill(context.RequestContext(),
                                            sub, action_time, remarks)
                self._create_cron_job(sub.get('subscription_id'), action_time)


def master():
    prepare_service()
    os_service.launch(MasterService()).wait()
