import pecan
from pecan import rest
from wsmeext.pecan import wsexpose

from oslo.config import cfg
from gringotts.api.v1 import models
from gringotts.db import models as db_models


class ProductsController(rest.RestController):
    @wsexpose(models.Product, body=models.Product)
    def post(self, data):
        # FIXME(suo): we should use db models that not bind to
        # any particular backends.
        db_conn = pecan.request.db_conn
        return db_conn.create_product(data.as_dict())

    @wsexpose([models.Product])
    def get_all(self):
        return [models.Product.sample()]

    @wsexpose(models.Product, unicode)
    def get_one(self, product_id):
        return models.Product.sample()
