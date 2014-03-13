from oslo.config import cfg

from gringotts import context
from gringotts import db
from gringotts import exception

from gringotts.openstack.common import log
from gringotts.openstack.common.rpc import service as rpc_service
from gringotts.openstack.common import service as os_service
from gringotts.openstack.common import timeutils

from gringotts.service import prepare_service


TIMESTAMP_TIME_FORMAT = '%Y-%m-%d %H:%M:%S.%f'

LOG = log.getLogger(__name__)

OPTS = []

cfg.CONF.register_opts(OPTS, group="worker")

cfg.CONF.import_opt('worker_topic', 'gringotts.worker.rpcapi',
                    group='worker')


class WorkerService(rpc_service.Service):

    def __init__(self, *args, **kwargs):
        kwargs.update(
            host=cfg.CONF.host,
            topic=cfg.CONF.worker.worker_topic,
        )
        self.db_conn = db.get_connection(cfg.CONF)
        self.ctxt = context.get_admin_context()
        super(WorkerService, self).__init__(*args, **kwargs)

    def start(self):
        super(WorkerService, self).start()
        # Add a dummy thread to have wait() working
        self.tg.add_timer(604800, lambda: None)

    def create_bill(self, ctxt, order_id, action_time=None, remarks=None):
        if isinstance(action_time, basestring):
            action_time = timeutils.parse_strtime(action_time,
                                                  fmt=TIMESTAMP_TIME_FORMAT)
        try:
            self.db_conn.create_bill(ctxt, order_id, action_time=action_time,
                                     remarks=remarks)
            LOG.debug('Create bill for order %s successfully.' % order_id)
        except Exception:
            LOG.exception('Fail to create bill for the order: %s' % order_id)
            raise exception.BillCreateFailed(order_id=order_id)

    def close_bill(self, ctxt, order_id, action_time):
        if isinstance(action_time, basestring):
            action_time = timeutils.parse_strtime(action_time,
                                                  fmt=TIMESTAMP_TIME_FORMAT)
        try:
            self.db_conn.close_bill(ctxt, order_id, action_time)
            LOG.debug('Close bill for order %s successfully.' % order_id)
        except Exception:
            LOG.exception('Fail to close bill for the order: %s' % order_id)
            raise exception.BillCloseFailed(order_id=order_id)

    def destory_resource(self, ctxt, order_id):
        LOG.debug('Destroy the resource because of owed')


def worker():
    prepare_service()
    os_service.launch(WorkerService()).wait()
