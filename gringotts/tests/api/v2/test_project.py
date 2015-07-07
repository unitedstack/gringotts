
import mock

from gringotts.openstack.common import log as logging
from gringotts.services import keystone
from gringotts.tests import rest

LOG = logging.getLogger(__name__)


class ProjectTestCase(rest.RestfulTestCase):

    def setUp(self):
        super(ProjectTestCase, self).setUp()

        self.project_path = '/v2/projects'
        self.headers = self.build_admin_http_headers()

    def build_user_projects_query_url(self, user_id=None, type=None):
        path = '/v2/projects'
        if user_id is None and type is None:
            return path
        path += '?'
        params = []
        if user_id:
            params.append('user_id=%s' % user_id)
        if type:
            params.append('type=%s' % type)

        return path + '&'.join(params)

    def build_project_query_url(self, project_id, custom=None):
        return self.build_query_url(self.project_path, project_id, custom)

    def test_get_project_by_id(self):
        project_ref = self.new_project_ref(
            user_id=self.admin_account.user_id,
            project_id=self.admin_account.project_id,
            domain_id=self.admin_account.domain_id
        )
        query_url = self.build_project_query_url(project_ref['project_id'])
        resp = self.get(query_url, headers=self.headers)
        project = resp.json_body
        self.assertProjectEqual(project_ref, project)

    def test_create_project(self):
        project_ref = self.new_project_ref()
        self.post(self.project_path, headers=self.headers,
                  body=project_ref, expected_status=204)

        project = self.dbconn.get_project(self.admin_req_context,
                                          project_ref['project_id'])
        self.assertProjectEqual(project_ref, project.as_dict())

        user_projects = self.dbconn.get_user_projects(
            self.admin_req_context, project_ref['user_id'])
        # TODO(liuchenhong): assert user_projects
        self.assertEqual(1, len(user_projects))

    def test_demo_user_get_payed_projects(self):
        user_id = self.demo_account.user_id
        project_id = self.demo_account.project_id
        domain_id = self.demo_account.domain_id
        headers = self.build_http_headers(
            user_id=user_id, user_name=self.demo_user_name,
            project_id=project_id, domain_id=domain_id, roles='demo'
        )
        ks_project = self.build_project_info_from_keystone(
            project_id, project_id, self.demo_account.domain_id,
            user_id, self.demo_user_name,
            user_id, self.demo_user_name,
            user_id, self.demo_user_name
        )

        query_url = self.build_user_projects_query_url(user_id, 'pay')
        with mock.patch.object(keystone, 'get_projects_by_project_ids',
                               return_value=[ks_project]):
            resp = self.get(query_url, headers=headers)

        user_projects = resp.json_body
        self.assertEqual(1, len(user_projects))
        self.assertInUserProjectsList(user_id, project_id, user_projects)

    def test_demo_user_get_all_projects(self):
        user_id = self.demo_account.user_id
        project_id = self.demo_account.project_id
        domain_id = self.demo_account.domain_id
        headers = self.build_http_headers(
            user_id=user_id, user_name=self.demo_user_name,
            project_id=project_id, domain_id=domain_id, roles='demo'
        )

        ks_project1 = self.build_project_info_from_keystone(
            project_id, project_id, self.demo_account.domain_id,
            user_id, self.demo_user_name,
            user_id, self.demo_user_name,
            user_id, self.demo_user_name
        )

        user_id2 = self.admin_account.user_id
        project_id2 = self.admin_account.project_id
        domain_id2 = self.admin_account.domain_id
        ks_project2 = self.build_project_info_from_keystone(
            project_id2, project_id2, domain_id2,
            user_id2, self.admin_user_name,
            user_id2, self.admin_user_name,
            user_id2, self.admin_user_name
        )

        query_url = self.build_user_projects_query_url(user_id, 'all')
        with mock.patch.object(keystone, 'get_projects_by_user',
                               return_value=[ks_project1, ks_project2]):
            resp = self.get(query_url, headers=headers)

        user_projects = resp.json_body
        self.assertEqual(2, len(user_projects))
        self.assertInUserProjectsList(user_id, project_id, user_projects)
        self.assertInUserProjectsList(user_id, project_id2, user_projects)

    def test_admin_user_get_payed_projects(self):
        user_id = self.admin_account.user_id
        project_id = self.admin_account.project_id
        ks_project = self.build_project_info_from_keystone(
            project_id, project_id, self.admin_account.domain_id,
            user_id, self.admin_user_name,
            user_id, self.admin_user_name,
            user_id, self.admin_user_name
        )

        query_url = self.build_user_projects_query_url(user_id, 'pay')
        with mock.patch.object(keystone, 'get_projects_by_project_ids',
                               return_value=[ks_project]):
            resp = self.get(query_url, headers=self.headers)

        user_projects = resp.json_body
        self.assertEqual(1, len(user_projects))
        self.assertInUserProjectsList(user_id, project_id, user_projects)

    def test_admin_user_get_all_projects(self):
        user_id = self.admin_account.user_id
        project_id = self.admin_account.project_id
        ks_project1 = self.build_project_info_from_keystone(
            project_id, project_id, self.admin_account.domain_id,
            user_id, self.admin_user_name,
            user_id, self.admin_user_name,
            user_id, self.admin_user_name
        )

        user_id2 = self.demo_account.user_id
        project_id2 = self.demo_account.project_id
        ks_project2 = self.build_project_info_from_keystone(
            project_id2, project_id2, self.demo_account.domain_id,
            user_id2, self.demo_user_name,
            user_id2, self.demo_user_name,
            user_id2, self.demo_user_name
        )

        query_url = self.build_user_projects_query_url(user_id, 'all')
        with mock.patch.object(keystone, 'get_projects_by_user',
                               return_value=[ks_project1, ks_project2]):
            resp = self.get(query_url, headers=self.headers)

        user_projects = resp.json_body
        self.assertEqual(2, len(user_projects))
        self.assertInUserProjectsList(user_id, project_id, user_projects)
        self.assertInUserProjectsList(user_id, project_id2, user_projects)

    def test_change_billing_owner(self):
        project_id = self.admin_account.project_id
        new_owner = {'user_id': self.admin_account.user_id}
        query_url = self.build_project_query_url(project_id, 'billing_owner')
        self.put(query_url, headers=self.headers, body=new_owner)
