from gringotts.api.v1 import product


class V1Controller(object):
    """Version 1 API controller root
    """
    products = product.ProductsController()
