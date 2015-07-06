
from __future__ import absolute_import

import fixtures
import mock
from oslo_config import cfg

from gringotts.db import impl_sqlalchemy
from gringotts.db.sqlalchemy import models as sql_models
from gringotts.openstack.common.db.sqlalchemy import session as db_session


CONF = cfg.CONF


def cleanup():
    db_session.cleanup()


def get_engine():
    return db_session.get_engine()


def get_session():
    return db_session.get_session()


class Database(fixtures.Fixture):
    """A fixture for setting up and tearing down a database"""

    IN_MEM_DB_CONNECTION_STRING = 'sqlite://'

    def __init__(self):
        super(Database, self).__init__()
        self._init_sql_session()
        self._load_sqlalchemy_models()

    def setUp(self):
        super(Database, self).setUp()

        self.engine = get_engine()
        self.addCleanup(delattr, self, 'engine')
        self.addCleanup(cleanup)

        sql_models.Base.metadata.create_all(bind=self.engine)
        self.addCleanup(sql_models.Base.metadata.drop_all, bind=self.engine)

    def _init_sql_session(self):
        # TODO(liuchenhong): We should use db_options.set_defaults(),
        # bug currently this is confliced with openstack.common.db
        # db_options.set_defaults(CONF,
        #                         connection=self.IN_MEM_DB_CONNECTION_STRING)
        pass

    def _load_sqlalchemy_models(self):
        model_module = 'gringotts.db.sqlalchemy.models'
        __import__(model_module)


class DbConnection(fixtures.Fixture):
    """A fixture for using gringotts database connection"""

    def setUp(self):
        super(DbConnection, self).setUp()

        def mocked_connection_init(*args, **kwargs):
            pass
        with mock.patch.object(impl_sqlalchemy.Connection,
                               '__init__', mocked_connection_init):

            self.conn = impl_sqlalchemy.Connection(CONF)

        self.addCleanup(delattr, self, 'conn')
