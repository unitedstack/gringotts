
import pecan

from gringotts.openstack.common import uuidutils
from gringotts.tests import core as tests
from gringotts.tests import gring_fixtures


class RestfulTestCase(tests.TestCase):

    def setUp(self):
        super(RestfulTestCase, self).setUp()

        self.config_fixture.config(
            group='database',
            connection=gring_fixtures.Database.IN_MEM_DB_CONNECTION_STRING)
        self.useFixture(gring_fixtures.Database())
        self.dbconn_fixture = self.useFixture(gring_fixtures.DbConnection())

        self.app_config, self.app = self.load_test_app(enable_acl=False)
        self.addCleanup(delattr, self, 'app_config')
        self.addCleanup(delattr, self, 'app')

    def load_test_app(self, enable_acl=False):
        app_config = {
            'app': {
                'root': 'gringotts.api.root.RootController',
                'modules': ['gringotts.api'],
                'static_root': '%s/public' % (self.root_path),
                'template_path': '%s/gringotts/api/templates' % (
                    self.root_path),
                'enable_acl': enable_acl,
            },
            'wsme': {
                'debug': True,
            },
        }

        return app_config, pecan.testing.load_test_app(app_config)

    def get_dbconn(self):
        return self.dbconn_fixture.conn

    def load_sample_data(self):
        pass

    def build_http_headers(self, auth_token=None, user_id=None, user_name=None,
                           project_id=None, domain_id=None, roles=None):
        headers = {}
        if not auth_token:
            auth_token = uuidutils.generate_uuid()
        headers['X-Auth-Token'] = auth_token
        if user_id:
            headers['X-User-Id'] = user_id
        if user_name:
            headers['X-User-Name'] = user_name
        if project_id:
            headers['X-Project-Id'] = project_id
        if domain_id:
            headers['X-Domain-Id'] = domain_id
        if roles:
            headers['roles'] = roles

        return headers

    def build_admin_http_headers(self, project_id=None, domain_id=None):
        return self.build_http_headers(
            user_name='admin', roles='admin',
            project_id=project_id, domain_id=domain_id)
