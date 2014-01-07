import pecan
import wsme
import datetime

from pecan import rest
from pecan import request
from wsmeext.pecan import wsexpose
from wsme import types as wtypes

from oslo.config import cfg

from gringotts import exception
from gringotts.api.v1 import models
from gringotts.db import models as db_models
from gringotts.openstack.common import log
from gringotts.openstack.common import uuidutils


LOG = log.getLogger(__name__)


class ProductController(rest.RestController):
    """Manages operations on a single product
    """

    def __init__(self, product_id):
        pecan.request.context['product_id'] = product_id
        self._id = product_id

    def _product(self):
        self.conn = pecan.request.db_conn
        try:
            product = self.conn.get_product(request.context,
                                            product_id=self._id)
        except Exception as e:
            LOG.error('Product %s not found' % self._id)
            raise exception.ProductIdNotFound(product_id=self._id)
        return product

    @wsexpose(models.Product, wtypes.text)
    def get(self):
        """Return this product"""
        return models.Product.from_db_model(self._product())

    @wsexpose(None, wtypes.text, status_code=204)
    def delete(self):
        """Delete this product"""
        # ensure product exists before deleting
        product = self._product()
        try:
            self.conn.delete_product(request.context, product.product_id)
        except Exception as e:
            error = 'Error while deleting product: %s' % product.product_id
            LOG.exception(error)
            raise exception.DBError(reason=error)

    @wsexpose(models.Product, wtypes.text, body=models.Product)
    def put(self, data):
        """Modify this product. PUT method will override all the fields.
        """
        # Ensure this product exists
        # NOTE(suo): we can't make product_in and product_old
        # point to the same object
        product_in = self._product()
        product_old = self._product()

        for k, v in data.as_dict().items():
            product_in[k] = v

        product_in.updated_at = datetime.datetime.utcnow()

        # Check if there are other same names in the same region
        # except itself
        filters = {'name': product_in.name,
                   'service': product_in.service,
                   'region_id': product_in.region_id}
        products = list(self.conn.get_products(request.context, filters=filters))

        if len(products) > 0 and (product_old.name != product_in.name or
                                  product_old.service != product_in.service or
                                  product_old.region_id != product_in.region_id):
            error = "Product with name(%s) within service(%s) already "\
                    "exists in region_id(%s)" % \
                    (data.name, data.service, data.region_id)
            LOG.warning(error)
            raise exception.DuplicatedProduct(reason=error)

        # Update product model to DB
        try:
            product = self.conn.update_product(request.context, product_in)
        except Exception as e:
            error = 'Error while updating product: %s' % data.as_dict()
            LOG.exception(error)
            raise exception.DBError(reason=error)

        # DB model to API model
        return models.Product.from_db_model(product)


class ProductsController(rest.RestController):
    """Manages operations on the products collection
    """
    @pecan.expose()
    def _lookup(self, product_id, *remainder):
        if remainder and not remainder[-1]:
            remainder = remainder[:-1]
        return ProductController(product_id), remainder

    @wsexpose(models.Product, body=models.Product)
    def post(self, data):
        """Create a new product
        """
        data.product_id = uuidutils.generate_uuid()
        conn = pecan.request.db_conn

        # API model to DB model
        try:
            product_in = db_models.Product(quantity=0,
                                           total_price=0,
                                           deleted=False,
                                           **data.as_dict())
        except Exception as e:
            error = 'Error while turning product: %s' % data.as_dict()
            LOG.exception(error)
            raise exception.MissingRequiredParams(reason=error)

        # Check if there are duplicated name in the same region
        filters = {'name': data.name,
                   'service': data.service,
                   'region_id': data.region_id}

        products = list(conn.get_products(request.context, filters=filters))

        if len(products) > 0:
            error = "Product with name(%s) within service(%s) already "\
                    "exists in region_id(%s)" % \
                    (data.name, data.service, data.region_id)
            LOG.warning(error)
            raise exception.DuplicatedProduct(reason=error)

        # Write product model to DB
        try:
            product = conn.create_product(request.context, product_in)
        except Exception as e:
            error = 'Error while creating product: %s' % data.as_dict()
            LOG.exception(error)
            raise exception.DBError(reason=error)

        # DB model to API model
        return models.Product.from_db_model(product)

    @wsexpose([models.Product], wtypes.text, wtypes.text, wtypes.text,
              int, wtypes.text, wtypes.text, wtypes.text)
    def get_all(self, name=None, service=None, region_id=None,
                limit=None, marker=None,
                sort_key='created_at', sort_dir='desc'):
        """Get all product
        """
        filters = {}
        if name:
            filters.update(name=name)
        if service:
            filters.update(service=service)
        if region_id:
            filters.update(region_id=region_id)

        conn = pecan.request.db_conn

        result = conn.get_products(request.context,
                                   filters=filters,
                                   limit=limit,
                                   marker=marker,
                                   sort_key=sort_key,
                                   sort_dir=sort_dir)
        return [models.Product.from_db_model(p) for p in result]
