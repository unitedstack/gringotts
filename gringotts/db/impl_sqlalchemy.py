"""SQLAlchemy storage backend."""

from gringotts.db import base
from gringotts.db import models as api_models

from gringotts.db.sqlalchemy import migration
from gringotts.db.sqlalchemy import models as sa_models
from gringotts.db.sqlalchemy.models import Base

from gringotts.openstack.common import log
from gringotts.openstack.common.db.sqlalchemy import session as sqlalchemy_session


LOG = log.getLogger(__name__)


class SQLAlchemyStorage(base.StorageEngine):
    """Put the data into a SQLAlchemy database.
    """

    @staticmethod
    def get_connection(conf):
        """Return a Connection instance based on the configuration settings.
        """
        return Connection(conf)


class Connection(base.Connection):
    """SqlAlchemy connection."""

    def __init__(self, conf):
        url = conf.database.connection
        if url == 'sqlite://':
            conf.database.connection = \
                os.environ.get('CEILOMETER_TEST_SQL_URL', url)

    def upgrade(self):
        migration.db_sync()

    def clear(self):
        session = sqlalchemy_session.get_session()
        engine = session.get_bind()
        for table in reversed(Base.metadata.sorted_tables):
            engine.execute(table.delete())

    def create_product(self, product):
        session = sqlalchemy_session.get_session()
        with session.begin():
            product_ref = sa_models.Product()
            product_ref.update(product)
            session.add(product_ref)
        return  product_ref
