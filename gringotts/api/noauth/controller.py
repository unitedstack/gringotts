from pecan import rest

from wsmeext.pecan import wsexpose
from gringotts.api.noauth import account
from gringotts.api.noauth import product
from gringotts.api.noauth import project
from gringotts.api.v2 import models


class NoAuthController(rest.RestController):
    """No Auth API controller root
    """
    products = product.ProductsController()
    accounts = account.AccountsController()
    projects = project.ProjectsController()

    @wsexpose(models.Version)
    def get(self):
        """Return the version info when request the root path
        """
        return models.Version(version='noauth')
