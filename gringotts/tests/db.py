"""Base class for database"""

from gringotts import db

from gringotts.tests import base as test_base
from gringotts.openstack.common.fixture import config


class DBTestBase(test_base.TestBase):

    def setUp(self):
        super(DBTestBase, self).setUp()

        self.CONF = self.useFixture(config.Config()).conf
        #url = 'mysql://root:rachel@localhost/test'
        url = 'sqlite://'
        self.CONF.set_override('connection', url, group='database')

        self.conn = db.get_connection(self.CONF)
        self.conn.upgrade()

        # Parse command line arguments and config files.
        # If it can't find command line arguments or config files,
        # it will use default option values
        self.CONF([], project='gringotts')

    def tearDown(self):
        super(DBTestBase, self).tearDown()

        self.conn.clear()
        self.conn = None
