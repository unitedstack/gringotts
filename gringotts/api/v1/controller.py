from pecan import rest
from wsmeext.pecan import wsexpose

from gringotts.api.v1 import product
from gringotts.api.v1 import order
from gringotts.api.v1 import account
from gringotts.api.v1 import bill
from gringotts.api.v1 import sub
from gringotts.api.v1 import precharge
from gringotts.api.v1 import fix
from gringotts.api.v1 import resource
from gringotts.api.v1 import project

from gringotts.api.v1 import models


class V1Controller(rest.RestController):
    """Version 1 API controller root
    """
    products = product.ProductsController()
    accounts = account.AccountsController()
    orders = order.OrdersController()
    bills = bill.BillsController()
    subs = sub.SubsController()
    precharge = precharge.PrechargesController()
    fix = fix.FixController()
    resources = resource.ResourcesController()
    projects = project.ProjectsController()

    @wsexpose(models.Version)
    def get(self):
        """Return the version info when request the root path
        """
        return models.Version(version='0.2.x')
