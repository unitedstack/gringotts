from gringotts.api.v1 import product
from gringotts.api.v1 import order
from gringotts.api.v1 import account
from gringotts.api.v1 import bill
from gringotts.api.v1 import sub
from gringotts.api.v1 import precharge
from gringotts.api.v1 import fix
from gringotts.api.v1 import resource


class V1Controller(object):
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
