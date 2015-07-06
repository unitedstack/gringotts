
import logging
import os.path

import fixtures
import mock
from oslo_config import cfg
from oslo_config import fixture as config_fixture
from oslotest import base
from oslotest import mockpatch

from gringotts.client.auth import token as token_auth_plugin


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


class TestCase(BaseTestCase):

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

    def setUp(self):
        super(TestCase, self).setUp()

        self.config_fixture = self.useFixture(config_fixture.Config(CONF))
        self.addCleanup(delattr, self, 'config_fixture')

        self.config(self.config_files())
        self.config_override()

        self.useFixture(fixtures.FakeLogger(level=logging.DEBUG))

        self.load_token_auth_plugin()

    def load_token_auth_plugin(self):
        """Mock the TokenAuthPlugin.

        Mock the TokenAuthPlugin to get rid of keystone server.
        """
        self.token_auth_plugin = mock.Mock(name='token_auth_plugin')
        self.useFixture(mockpatch.PatchObject(
            token_auth_plugin, 'TokenAuthPlugin'))
