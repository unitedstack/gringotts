from pecan import rest

from wsmeext.pecan import wsexpose
from gringotts.api.noauth import product
from gringotts.api.v2 import models


class NoAuthController(object):
    """No Auth API controller root
    """
    products = product.ProductsController()

    @wsexpose(models.Version)
    def get(self):
        """Return the version info when request the root path
        """
        return models.Version(version='noauth')
