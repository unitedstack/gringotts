"""
Alembic Migrations
"""

import alembic
from alembic import config as alembic_config

from gringotts.openstack.common import log


LOG = log.getLogger(__name__)


def db_sync(engine):
    alembic.command.upgrade(_alembic_config(), "head")


def _alembic_config():
    path = os.path.join(os.path.dirname(__file__), 'alembic/alembic.ini')
    config = alembic_config.Config(path)
    return config
