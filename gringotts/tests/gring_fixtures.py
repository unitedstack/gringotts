
from __future__ import absolute_import

import copy

import fixtures
from oslo_config import cfg

from gringotts.db import impl_sqlalchemy
from gringotts.db import models as db_models
from gringotts.db.sqlalchemy import models as sql_models
from gringotts.openstack.common.db.sqlalchemy import session as db_session
from gringotts.openstack.common import uuidutils
from gringotts.tests import fake_data as test_data


CONF = cfg.CONF


def cleanup():
    db_session.cleanup()


def get_engine():
    return db_session.get_engine()


def get_session():
    return db_session.get_session()


def delete_all_rows(model):
    session = get_session()
    session.query(model).delete()


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

        # Create all tables from sqlalchemy models
        sql_models.Base.metadata.create_all(bind=self.engine)
        self.addCleanup(sql_models.Base.metadata.drop_all, bind=self.engine)

        self.conn = impl_sqlalchemy.Connection(CONF)
        self.addCleanup(delattr, self, 'conn')

    def _init_sql_session(self):
        # TODO(liuchenhong): We should use db_options.set_defaults(),
        # bug currently this is confliced with openstack.common.db
        # db_options.set_defaults(CONF,
        #                         connection=self.IN_MEM_DB_CONNECTION_STRING)
        pass

    def _load_sqlalchemy_models(self):
        model_module = 'gringotts.db.sqlalchemy.models'
        __import__(model_module)


class ProductTableData(fixtures.Fixture):
    """A fixture for inserting data into product table"""

    def __init__(self, dbconn, context):
        self.dbconn = dbconn
        self.context = context

    def build_product_model(self, name, service, description, unit_price,
                            unit, quantity=0, extra=None, product_id=None,
                            region_id='RegionOne', type='regular',
                            deleted=False):

        if not product_id:
            product_id = uuidutils.generate_uuid()

        created_at = None
        updated_at = None
        deleted_at = None

        return db_models.Product(
            product_id=product_id, name=name, service=service,
            unit_price=unit_price, unit=unit, extra=extra,
            description=description, quantity=quantity,
            region_id=region_id, type=type, deleted=deleted,
            created_at=created_at, updated_at=updated_at,
            deleted_at=deleted_at)

    def _generate_products(self, products_list):
        products = []
        for product in products_list:
            product_model = self.build_product_model(**product)
            self.dbconn.create_product(self.context, product_model)
            products.append(
                self.dbconn.get_product_by_name(
                    self.context, product_model.name,
                    product_model.service, product_model.region_id
                )
            )
        return products

    def setUp(self):
        super(self.__class__, self).setUp()

        self.instance_products = self._generate_products(
            test_data.instance_products)
        self.ip_products = self._generate_products(test_data.ip_products)

        self.total = len(self.ip_products) + len(self.instance_products)

        self.addCleanup(delete_all_rows, sql_models.Product)


class AccountAndProjectData(fixtures.Fixture):
    """A fixture for generating account and project data"""

    def __init__(self, dbconn, context,
                 user_id, project_id, domain_id, level, owed=False,
                 balance=0, consumption=0, inviter=None, sales_id=None):

        self.dbconn = dbconn
        self.context = context
        self.user_id = user_id
        self.project_id = project_id
        self.domain_id = domain_id
        self.level = level
        self.owed = owed
        self.inviter = inviter
        self.sales_id = sales_id
        self.balance = balance
        self.consumption = consumption

    def setUp(self):
        super(self.__class__, self).setUp()

        self.account = db_models.Account(
            user_id=self.user_id, project_id=self.project_id,
            domain_id=self.domain_id, balance=self.balance,
            consumption=self.consumption, level=self.level,
            inviter=self.inviter, sales_id=self.sales_id
        )
        self.dbconn.create_account(self.context, self.account)

        self.project = db_models.Project(
            user_id=self.user_id, project_id=self.project_id,
            domain_id=self.domain_id, consumption=0
        )
        self.dbconn.create_project(self.context, self.project)
        self.user_project = copy.deepcopy(self.project)

        self.addCleanup(delete_all_rows, sql_models.UserProject)
        self.addCleanup(delete_all_rows, sql_models.Project)
        self.addCleanup(delete_all_rows, sql_models.Account)


class WorkerFixture(fixtures.Fixture):

    def __init__(self, app):
        self.app = app
