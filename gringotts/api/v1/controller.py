from pecan import rest
from wsmeext.pecan import wsexpose

from oslo.config import cfg
from gringotts.api.v1 import models


class TestController(rest.RestController):
    @wsexpose(models.Time)
    def get_all(self):
        return models.Time(value=5.3, unit='hour')


class V1Controller(object):
    """Version 1 API controller root
    """
    test = TestController()
