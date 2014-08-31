import datetime

from gringotts.tests import db_fixtures
from gringotts.tests import fake_data
from gringotts.tests.api.v1 import FunctionalTest


class TestProjects(FunctionalTest):
    PATH = '/projects'

    def setUp(self):
        super(TestProjects, self).setUp()
        self.useFixture(db_fixtures.DatabaseInit(self.conn))
        self.headers = {'X-Roles': 'admin'}

    def test_get_projects(self):
        data = self.get_json(self.PATH, headers=self.headers)
        self.assertEqual(2, data['total_count'])

    def test_get_projects_by_user_id(self):
        data = self.get_json(self.PATH, headers=self.headers,
                             user_id=fake_data.ADMIN_USER_ID)
        self.assertEqual(2, data['total_count'])

    def test_get_project(self):
        path = self.PATH + '/' + fake_data.ADMIN_PROJECT_ID
        data = self.get_json(path, headers=self.headers)
        self.assertEqual(fake_data.ADMIN_USER_ID, data['user_id'])
        self.assertEqual(fake_data.ADMIN_PROJECT_ID, data['project_id'])

    def test_post_project(self):
        body = {
            "user_id": fake_data.DEMO_USER_ID,
            "project_id": "fake_project_id",
            "domain_id": "fake_domain_id",
            "consumption": "0"
        }
        self.post_json(self.PATH, body, headers=self.headers)

        data = self.get_json(self.PATH, headers=self.headers)
        self.assertEqual(3, data['total_count'])
