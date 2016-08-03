"""Base classes for storage engines
"""
import abc

from oslo_db import concurrency as db_concurrency
from oslo_config import cfg


CONF = cfg.CONF

_BACKEND_MAPPING = {'sqlalchemy': 'gringotts.db.sqlalchemy.api'}
IMPL = db_concurrency.TpoolDbapiWrapper(CONF, _BACKEND_MAPPING)


def get_instance():
    """Return a DB API instance."""
    return IMPL


class StorageEngine(object):
    """Base class for storage engines."""

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def get_connection(self, conf):
        """Return a Connection instance based on the configuration settings."""


class Connection(object):
    """Base class for storage system connections."""

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def __init__(self, conf):
        """Constructor."""

    @abc.abstractmethod
    def upgrade(self):
        """Migrate the database to `version` or the most recent version."""
