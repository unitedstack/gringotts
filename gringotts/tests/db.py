"""Base class for database"""
import mock
from gringotts import db

from gringotts.tests import base as test_base
from gringotts.openstack.common.fixture import config


class DBTestBase(test_base.TestBase):

    def setUp(self):
        super(DBTestBase, self).setUp()

        self.CONF = self.useFixture(config.Config()).conf

        # Parse command line arguments and config files.
        # If it can't find command line arguments or config files,
        # it will use default option values
        self.CONF([], project='gringotts')

        #url = 'mysql://root:rachel@localhost/test'
        url = 'sqlite://'
        self.CONF.set_override('connection', url, group='database')

        with mock.patch('gringotts.services.keystone.get_admin_user_id', return_value='mock_user_id'):
            with mock.patch('gringotts.services.keystone.get_admin_tenant_id', return_value='mock_project_id'):
                self.conn = db.get_connection(self.CONF)
                self.conn.upgrade()

    def tearDown(self):
        super(DBTestBase, self).tearDown()

        self.conn.clear()
        self.conn = None
