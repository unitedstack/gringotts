import mock
import datetime

from gringotts.tests import db_fixtures
from gringotts.tests import fake_data
from gringotts.tests.api.v2 import FunctionalTest


class TestProjects(FunctionalTest):
    PATH = '/projects'

    def setUp(self):
        super(TestProjects, self).setUp()
        self.useFixture(db_fixtures.DatabaseInit(self.conn))
        self.headers = {'X-Roles': 'admin'}

    def test_get_pay_projects(self):
        with mock.patch('gringotts.services.keystone.get_projects_by_project_ids', return_value=fake_data.USER_PROJECTS):
            data = self.get_json(self.PATH, headers=self.headers,
                                 type='pay', user_id=fake_data.ADMIN_USER_ID)
        self.assertEqual(2, len(data))
        self.assertEqual(fake_data.ADMIN_USER_ID, data[0]['billing_owner']['user_id'])
        self.assertEqual(fake_data.ADMIN_USER_ID, data[1]['billing_owner']['user_id'])

    def test_get_all_projects(self):
        with mock.patch('gringotts.services.keystone.get_projects_by_user', return_value=fake_data.USER_PROJECTS):
            data = self.get_json(self.PATH, headers=self.headers,
                                 type='all', user_id=fake_data.ADMIN_USER_ID)
        self.assertEqual(2, len(data))
        self.assertEqual(fake_data.ADMIN_USER_ID, data[0]['billing_owner']['user_id'])
        self.assertEqual(fake_data.ADMIN_USER_ID, data[1]['billing_owner']['user_id'])

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

        path = self.PATH + '/fake_project_id'
        data = self.get_json(path, headers=self.headers)
        self.assertEqual(fake_data.DEMO_USER_ID, data['user_id'])
        self.assertEqual('fake_project_id', data['project_id'])

    def test_change_billing_owner(self):
        self.useFixture(db_fixtures.GenerateFakeData(self.conn))
        body = {"user_id": fake_data.DEMO_USER_ID}
        path = self.PATH + '/' + fake_data.DEMO_PROJECT_ID + '/billing_owner'
        self.put_json(path, body, headers=self.headers)

        path = self.PATH + '/' + fake_data.DEMO_PROJECT_ID
        data = self.get_json(path, headers=self.headers)
        self.assertEqual(fake_data.DEMO_USER_ID, data['user_id'])
        self.assertEqual(fake_data.DEMO_PROJECT_ID, data['project_id'])
