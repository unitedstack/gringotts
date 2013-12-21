from oslo.config import cfg
from stevedore import extension

from datetime import datetime, timedelta
from apscheduler.scheduler import Scheduler as APScheduler

from gringotts import db
from gringotts import worker

from gringotts.service import prepare_service
from gringotts.openstack.common import log
from gringotts.openstack.common import service as os_service
from gringotts.openstack.common.rpc import service as rpc_service


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
        super(MasterService, self).__init__(*args, **kwargs)

    def start(self):
        super(MasterService, self).start()
        self.apsched.start()
        # Add a dummy thread to have wait() working
        self.tg.add_timer(604800, lambda: None)

    def _pre_deduct(self, subscription):
        self.worker_api.pre_deduct(subscription)

    def _back_deduct(self, subscription):
        self.worker_api.back_deduct(subscription)

    def _create_cron_job(self, subscription, action_time):
        """For now, we only supprot hourly cron job"""
        self.apsched.add_interval_job(_pre_deduct,
                                      hours=1, # interval
                                      start_date=action_time+timedelta(hours=1),
                                      args=[subscirption])

    def _update_cron_job(self):
        pass

    def _delete_cron_job(self):
        pass

    def resource_created(self, ctxt, subs_products, action_time, remarks):
        LOG.debug('Resource created')

        for sub, product in subs_products:
            # Create a bill for this subscription
            self.worker_api.create_bill(sub, product, action_time, remarks)

            # Create a cron job for this subscription
            self._create_cron_job(sub, action_time)

    def resource_deleted(self, ctxt, values):
        LOG.debug('Instance deleted: %s' % values)
        self._back_charge()
        self._delete_cron_job()

    def resource_changed(self, ctxt, values):
        LOG.debug('Instance changed: %s' % values)
        self._back_charge()
        self._pre_charge()
        self._update_cron_job()


def master():
    prepare_service()
    os_service.launch(MasterService()).wait()
