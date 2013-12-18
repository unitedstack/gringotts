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

    def _pre_deduct(self):
        self.worker_api.pre_deduct()

    def _back_deduct(self):
        self.worker_api.back_deduct()

    def _create_cron_job(self, launched_at, period, *args, **kwargs):
        if period == 'hourly':
            self.apsched.add_interval_job(_pre_deduct, hours=1,
                                          start_date=launched_at+timedelta(hours=1),
                                          args=args, kwargs=kwargs)
        elif period == 'dayly':
            self.apsched.add_interval_job(_pre_deduct, days=1,
                                          start_date=launched_at+timedelta(days=1),
                                          args=args, kwargs=kwargs)
        elif period == 'monthly':
            self.apsched.add_interval_job(_pre_deduct, weeks=4,
                                          start_date=launched_at+timedelta(weeks=4),
                                          args=args, kwargs=kwargs)
        elif period == 'yearly':
            self.apsched.add_interval_job(_pre_deduct, weeks=48,
                                          start_date=launched_at+timedelta(weeks=48),
                                          args=args, kwargs=kwargs)

    def _update_cron_job(self):
        pass

    def _delete_cron_job(self):
        pass

    def instance_created(self, ctxt, message, subscription, product):
        LOG.debug('Instance created: %s' % values)

        launched_at = message['payload']['launched_at']
        period = product.period

        remarks = 'Instance has been created'

        # send a initialized bill command to worker for this subscription
        self.worker_api.init_bill(message, subscription, product, remarks)

        # create a cron job for this subscription
        self._create_cron_job(launched_at, period,
                              message, subscription, product)

    def instance_deleted(self, ctxt, values):
        LOG.debug('Instance deleted: %s' % values)
        self._back_charge()
        self._delete_cron_job()

    def instance_changed(self, ctxt, values):
        LOG.debug('Instance changed: %s' % values)
        self._back_charge()
        self._pre_charge()
        self._update_cron_job()


def master():
    prepare_service()
    os_service.launch(MasterService()).wait()
