from pecan import rest
from wsmeext.pecan import wsexpose

from gringotts.api.v1 import controller
from gringotts.api.v1 import models


class RootController(rest.RestController):

    v1 = controller.V1Controller()

    @wsexpose(models.Version)
    def get(self):
        """Return the version info when request the root path
        """
        return models.Version(version='0.0.1')
