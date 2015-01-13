from pecan import rest
from wsmeext.pecan import wsexpose

from gringotts.api.v2 import product
from gringotts.api.v2 import order
from gringotts.api.v2 import account
from gringotts.api.v2 import bill
from gringotts.api.v2 import sub
from gringotts.api.v2 import precharge
from gringotts.api.v2 import fix
from gringotts.api.v2 import resource
from gringotts.api.v2 import project
from gringotts.api.v2 import download
from gringotts.api.v2 import quotas
from gringotts.api.v2 import deduct

from gringotts.api.v2 import models


class V2Controller(rest.RestController):
    """Version 2 API controller root
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
    downloads = download.DownloadsController()
    quotas = quotas.QuotasController()
    pay = deduct.PayController()
    checkReq = deduct.CheckReqController()
    getBalance = deduct.GetBalanceController()

    @wsexpose(models.Version)
    def get(self):
        """Return the version info when request the root path
        """
        return models.Version(version='0.2.0')
