
from datetime import datetime
import logging
import os.path
import re
import uuid

import fixtures
import mock
from oslo_config import cfg
from oslo_config import fixture as config_fixture
from oslotest import base
from oslotest import mockpatch
import pecan.testing
import six
from testtools import matchers
import webtest
import webtest.debugapp

from gringotts.api.v2 import models as api_models
import gringotts.client.v2.client
from gringotts.client.auth import token as token_auth_plugin
import gringotts.context
from gringotts.db import models as db_models
from gringotts.openstack.common import jsonutils
from gringotts.openstack.common import timeutils
import gringotts.policy
from gringotts.tests import gring_fixtures
from gringotts import utils as gring_utils


CONF = cfg.CONF


def get_root_path():
    root_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..', '..'))
    return root_path


class BaseTestCase(base.BaseTestCase):
    """Base class for unit test classes."""

    def setUp(self):
        super(BaseTestCase, self).setUp()
        self.root_path = get_root_path()

    def clean_attr(self, attrs):
        if isinstance(attrs, str):
            self.addCleanup(delattr, self, attrs)
        elif isinstance(self, list):
            for attr in attrs:
                self.addCleanup(delattr, self, attr)

    def assertNotEqual(self, value1, value2):
        self.assertThat(value1, matchers.NotEquals(value2))

    def assertDecimalEqual(self, value1, value2):
        self.assertEqual(self.quantize(value1), self.quantize(value2))

    def fail(self, message='User caused failure'):
        self.assertEqual(1, 2, message)

    def new_uuid(self):
        return uuid.uuid4().hex

    def new_uuid4(self):
        return str(uuid.uuid4())


class TestCase(BaseTestCase):

    DATE_FORMAT = '%Y-%m-%d'
    TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S.%f'
    ISOTIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%f'
    LOG_FORMAT = '%(levelname)8s [%(name)s] %(message)s'

    def setUp(self):
        super(TestCase, self).setUp()

        self.config_fixture = self.useFixture(config_fixture.Config(CONF))
        self.clean_attr('config_fixture')

        self.config(self.config_files())
        self.config_override()

        # setup logger
        self.log_fixture = self.useFixture(
            fixtures.FakeLogger(level=logging.DEBUG, format=self.LOG_FORMAT))

        # setup database connection and admin context
        self.load_database()
        self.admin_req_context = self.build_admin_req_context()
        self.clean_attr('admin_req_context')

        # setup test app
        self.mock_token_auth_plugin()
        self.app_config, self.app = self.load_test_app()
        self.clean_attr(['app_config', 'app'])

        # setup sample data
        self.load_account_info()
        self.load_sample_data()

    def config_files(self):
        return []

    def config(self, config_files):
        CONF(args=[], project='gringotts', default_config_files=config_files)

    def config_override(self):
        # TODO(liuchenhong): gringotts use oslo-incubator policy module
        # which put policy_file config in default group.
        policy_file_path = os.path.join(self.root_path,
                                        'etc/gringotts/policy.json')
        self.config_fixture.config(policy_file=policy_file_path)

    def load_account_info(self):
        self.admin_user_id = self.new_user_id()
        self.admin_user_name = 'admin'
        self.demo_user_id = self.new_user_id()
        self.demo_user_name = 'demo'
        self.clean_attr(['admin_user_id', 'admin_user_name',
                         'demo_user_id', 'demo_user_name'])

        self.default_domain_id = 'default'
        self.demo_domain_id = self.new_domain_id()
        self.default_project_id = self.new_project_id()
        self.demo_project_id = self.new_project_id()
        self.clean_attr(['default_domain_id', 'demo_domain_id',
                         'default_project_id', 'demo_project_id'])

    def mock_token_auth_plugin(self):
        """Mock the TokenAuthPlugin.

        Mock the TokenAuthPlugin to get rid of keystone server.
        """
        self.token_auth_plugin = mock.MagicMock(name='token_auth_plugin')
        self.useFixture(mockpatch.PatchObject(
            token_auth_plugin, 'TokenAuthPlugin', self.token_auth_plugin
        ))

    def load_test_app(self, enable_acl=False):
        app_config = {
            'app': {
                'root': 'gringotts.api.root.RootController',
                'modules': ['gringotts.api'],
                'static_root': '%s/public' % self.root_path,
                'template_path': '%s/templates' % self.root_path,
                'enable_acl': enable_acl,
            },
            'wsme': {
                'debug': True,
            },
        }

        return app_config, pecan.testing.load_test_app(app_config)

    def load_database(self):
        self.config_fixture.config(
            group='database',
            connection=gring_fixtures.Database.IN_MEM_DB_CONNECTION_STRING
        )
        self.db_fixture = self.useFixture(gring_fixtures.Database())

    @property
    def dbconn(self):
        return self.db_fixture.conn

    def load_sample_data(self):
        # setup product sample data
        self.product_fixture = self.useFixture(
            gring_fixtures.ProductTableData(
                self.dbconn, self.admin_req_context)
        )

        # setup account data
        self.admin_account = self.useFixture(
            gring_fixtures.AccountAndProjectData(
                self.dbconn, self.admin_req_context,
                self.admin_user_id, self.default_project_id,
                self.default_domain_id, 9
            )
        )
        self.demo_account = self.useFixture(
            gring_fixtures.AccountAndProjectData(
                self.dbconn, self.admin_req_context,
                self.demo_user_id, self.demo_project_id,
                self.demo_domain_id, 3,
                inviter=self.admin_account.user_id,
            )
        )

    def assertLogging(self, restr):
        m = re.search(restr, self.log_fixture.output,
                      flags=re.MULTILINE)
        self.assertIsNotNone(m, 'No log matched regex: %s' % restr)

    def build_http_headers(self, auth_token=None, user_id=None,
                           user_name=None, project_id=None, domain_id=None,
                           roles=None):
        """Build HTTP headers sent from HTTP client"""
        headers = {}
        if not auth_token:
            auth_token = self.new_uuid4()
        headers['X-Auth-Token'] = auth_token
        if user_id:
            headers['X-User-Id'] = user_id
        if project_id:
            headers['X-Project-Id'] = project_id
        if domain_id:
            headers['X-Domain-Id'] = domain_id
        if roles:
            headers['X-Roles'] = roles

        return headers

    def build_admin_http_headers(self):
        return self.build_http_headers(user_id=self.admin_user_id,
                                       user_name=self.admin_user_name,
                                       roles='admin')

    def build_demo_http_headers(self):
        return self.build_http_headers(user_id=self.demo_user_id,
                                       user_name=self.demo_user_name,
                                       roles='demo')

    def build_req_context(auth_token=None, user_id=None, user_name=None,
                          project_id=None, domain_id=None,
                          is_admin=False, is_domain_owner=False,
                          request_id=None, roles=None):
        if not roles:
            # TODO(liuchenhong): default value of argument 'role' of
            # RequestContext.__init__ functions is [] which is not
            # recommended.
            roles = []

        context = gringotts.context.RequestContext(
            auth_token, user_id, user_name, project_id, domain_id,
            is_admin, is_domain_owner, request_id, roles
        )
        return context

    def build_admin_req_context(self):
        return gringotts.context.get_admin_context()

    def new_order_id(self):
        return self.new_uuid4()

    def new_resource_id(self):
        return self.new_uuid4()

    def new_project_id(self):
        return self.new_uuid()

    def new_user_id(self):
        return self.new_uuid()

    def new_domain_id(self):
        return self.new_uuid()

    def utcnow(self):
        return datetime.utcnow()

    def date_to_str(self, dt):
        return dt.strftime(self.DATE_FORMAT)

    def datetime_to_str(self, dt):
        return dt.strftime(self.TIMESTAMP_FORMAT)

    def datetime_to_isotime_str(self, dt):
        return dt.strftime(self.ISOTIME_FORMAT)

    def datetime_from_str(self, dt_str):
        return datetime.strptime(dt_str, self.TIMESTAMP_FORMAT)

    def datetime_from_isotime_str(self, isotime_str):
        return timeutils.parse_isotime(isotime_str)

    def quantize(self, value):
        return gring_utils._quantize_decimal(value)

    def create_subs_in_db(self, product, resource_volume, status, order_id,
                          project_id, user_id, region_id=CONF.region_name):
        self.assertIsInstance(product, db_models.Product)

        subs_ref = api_models.SubscriptionPostBody(
            service=product.service, product_name=product.name,
            resource_volume=resource_volume, type=status,
            region_id=region_id, project_id=project_id, user_id=user_id,
            order_id=order_id
        )
        subs = self.dbconn.create_subscription(self.admin_req_context,
                                               **subs_ref.as_dict())
        self.assertIsInstance(subs, db_models.Subscription)
        return subs

    def create_order_in_db(self, order_price, unit, user_id, project_id,
                           resource_type, status, order_id=None,
                           resource_id=None, resource_name=None,
                           region_id=CONF.region_name):
        if not order_id:
            order_id = self.new_order_id()
        if not resource_id:
            resource_id = self.new_resource_id()
        if not resource_name:
            resource_name = resource_id

        order_ref = api_models.OrderPostBody(
            order_id=order_id, unit=unit,
            unit_price=self.quantize(order_price),
            user_id=user_id, project_id=project_id, region_id=region_id,
            status=status, type=resource_type, resource_id=resource_id,
            resource_name=resource_name)
        order = self.dbconn.create_order(self.admin_req_context,
                                         **order_ref.as_dict())
        self.assertIsInstance(order, db_models.Order)
        return order

    def update_product_in_db(self, product_id, unit_price=None, extra=None):
        product = self.dbconn.get_product(self.admin_req_context,
                                          product_id)
        if unit_price:
            self.assertIsInstance(unit_price, six.text_type)
            product['unit_price'] = self.quantize(unit_price)

        if extra:
            if not isinstance(extra, six.text_type):
                product['extra'] = jsonutils.dumps(extra)
            else:
                product['extra'] = extra

        return self.dbconn.update_product(self.admin_req_context, product)


class MiddlewareTestCase(BaseTestCase):

    LOG_FORMAT = '%(levelname)8s [%(name)s] %(message)s'

    def setUp(self):
        super(MiddlewareTestCase, self).setUp()

        self.config_fixture = self.useFixture(config_fixture.Config(CONF))
        self.clean_attr('config_fixture')

        self.config(self.config_files())

        # setup logger
        self.log_fixture = self.useFixture(
            fixtures.FakeLogger(level=logging.DEBUG, format=self.LOG_FORMAT))
        self.mock_gringotts_client()

        self.environ = {'HTTP_X_USER_ID': self.new_uuid(),
                        'HTTP_X_PROJECT_ID': self.new_uuid(),
                        'HTTP_X_ROLES': '_member_'}

    def config_files(self):
        test_config_path = os.path.join(
            self.root_path,
            'gringotts/tests/config_files/middleware.conf')
        return [test_config_path]

    def config(self, config_files):
        CONF(args=[], project='gringotts', default_config_files=config_files)

    def load_middleware_app(self, filter_factory):
        app_factory = filter_factory({})
        return webtest.TestApp(app_factory(webtest.debugapp.debug_app))

    def mock_gringotts_client(self):
        self.mocked_client = mock.MagicMock(name='gringotts.client')
        self.useFixture(mockpatch.PatchObject(
            gringotts.client.v2.client, 'Client',
            return_value=self.mocked_client))

    def get(self, path, params=None, status=None):
        return self.app.get(path, params=params, extra_environ=self.environ,
                            status=status)

    def post_json(self, path, params={}, status=None):
        return self.app.post_json(path, params=params,
                                  extra_environ=self.environ, status=status)

    def put_json(self, path, params={}, status=None):
        return self.app.put_json(path, params=params,
                                 extra_environ=self.environ, status=status)

    def delete(self, path, params={}, status=None):
        return self.app.delete(path, params=params,
                               extra_environ=self.environ, status=status)

    def build_billing_owner(self, level=3, balance='0'):
        return {'level': level, 'balance': balance}

    def build_order(self, unit=None):
        return {'unit': unit, 'order_id': self.new_uuid4()}
