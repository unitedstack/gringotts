"""Base classes for storage engines
"""
import abc


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
