from gringotts.api.v1 import product
from gringotts.api.v1 import statistics
from gringotts.api.v1 import price
from gringotts.api.v1 import account


class V1Controller(object):
    """Version 1 API controller root
    """
    products = product.ProductsController()
    statistics = statistics.StatisticsController()
    price = price.PriceController()
    accounts = account.AccountsController()
