from oslo.config import cfg
from stevedore import extension

from gringotts.service import prepare_service
from gringotts.openstack.common import log
from gringotts.openstack.common import service as os_service
from gringotts.openstack.common.rpc import service as rpc_service


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
        super(WorkerService, self).__init__(*args, **kwargs)

    def start(self):
        super(WorkerService, self).start()
        # Add a dummy thread to have wait() working
        self.tg.add_timer(604800, lambda: None)

    def pre_charge(self, ctxt, values):
        LOG.debug('%s, you are here' % values)

def worker():
    prepare_service()
    os_service.launch(WorkerService()).wait()
