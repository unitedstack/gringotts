
from oslo_config import cfg

from gringotts.tests import service as test_service

CONF = cfg.CONF


class InstanceTestCase(test_service.WaiterServiceTestCase):

    def setUp(self):
        super(InstanceTestCase, self).setUp()

    def test_instance_created(self):
        pass

    def test_instance_stop(self):
        pass

    def test_instance_start(self):
        pass

    def test_instance_resize(self):
        pass

    def test_instance_delete(self):
        pass
