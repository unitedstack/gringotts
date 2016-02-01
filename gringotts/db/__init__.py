"""Storage backend management
"""

import urlparse

from oslo_config import cfg
from stevedore import driver

from gringotts.openstack.common import log
from gringotts import service


LOG = log.getLogger(__name__)

STORAGE_ENGINE_NAMESPACE = 'gringotts.storage'


cfg.CONF.import_opt('connection',
                    'gringotts.openstack.common.db.sqlalchemy.session',
                    group='database')


def get_engine(conf):
    """Load the configured engine and return an instance."""
    engine_name = urlparse.urlparse(conf.database.connection).scheme
    LOG.debug('looking for %r driver in %r',
              engine_name, STORAGE_ENGINE_NAMESPACE)
    mgr = driver.DriverManager(STORAGE_ENGINE_NAMESPACE,
                               engine_name,
                               invoke_on_load=True)
    return mgr.driver


def get_connection(conf):
    """Return an open connection to the database."""
    return get_engine(conf).get_connection(conf)


def dbsync():
    service.prepare_service()
    get_connection(cfg.CONF).upgrade()
