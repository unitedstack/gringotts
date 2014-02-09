"""Test base classes.
"""
import functools
import os.path

from gringotts.openstack.common import test


class TestBase(test.BaseTestCase):

    def setUp(self):
        super(TestBase, self).setUp()

    @staticmethod
    def path_get(project_file=None):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                            '..',
                                            '..',
                                            )
                               )
        if project_file:
            return os.path.join(root, project_file)
        else:
            return root
