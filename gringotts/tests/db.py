"""Base class for database"""

import fixtures

from gringotts import context
from gringotts import db
from gringotts.db import models as db_models

from gringotts.tests import base as test_base
from gringotts.tests import fake_data
from gringotts.openstack.common.fixture import config


class DatabaseInit(fixtures.Fixture):
    def __init__(self, conn):
        self.conn = conn

    def setUp(self):
        super(DatabaseInit, self).setUp()
        self.prepare_data()

    def prepare_data(self):
        product_flavor_tiny = db_models.Product(**fake_data.PRODUCT_FLAVOR_TINY)
        product_volume_size = db_models.Product(**fake_data.PRODUCT_VOLUME_SIZE)
        product_snapshot_size = db_models.Product(**fake_data.PRODUCT_SNAPSHOT_SIZE)
        product_image_license = db_models.Product(**fake_data.PRODUCT_IMAGE_LICENSE)

        fake_account = db_models.Account(**fake_data.FAKE_ACCOUNT)

        self.conn.create_product(context.get_admin_context(),
                                 product_flavor_tiny)
        self.conn.create_product(context.get_admin_context(),
                                 product_volume_size)
        self.conn.create_product(context.get_admin_context(),
                                 product_snapshot_size)
        self.conn.create_product(context.get_admin_context(),
                                 product_image_license)
        self.conn.create_account(context.get_admin_context(),
                                 fake_account)

class DBTestBase(test_base.TestBase):

    def setUp(self):
        super(DBTestBase, self).setUp()

        self.CONF = self.useFixture(config.Config()).conf
        #url = 'mysql://root:rachel@localhost/test'
        url = 'sqlite://'
        self.CONF.set_override('connection', url, group='database')

        self.conn = db.get_connection(self.CONF)
        self.conn.upgrade()

    def tearDown(self):
        super(DBTestBase, self).tearDown()

        self.conn.clear()
        self.conn = None
