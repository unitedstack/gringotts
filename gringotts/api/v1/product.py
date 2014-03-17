import pecan
import wsme
import datetime

from pecan import rest
from pecan import request
from wsmeext.pecan import wsexpose
from wsme import types as wtypes

from oslo.config import cfg

from gringotts import exception
from gringotts import utils as gringutils

from gringotts.api.v1 import models
from gringotts.db import models as db_models
from gringotts.openstack.common import log
from gringotts.openstack.common import uuidutils


LOG = log.getLogger(__name__)


class ProductController(rest.RestController):
    """Manages operations on a single product
    """
    _custom_actions = {
        'sales': ['GET'],
    }

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

    @wsexpose([models.Subscription], wtypes.text,
              datetime.datetime, datetime.datetime)
    def sales(self, start_time=None, end_time=None):
        """Return this product's subscriptions"""
        product = self._product()

        subs = self.conn.get_subscriptions_by_product_id(
            request.context,
            self._id,
            start_time=start_time,
            end_time=end_time)

        subscriptions = []
        for s in subs:
            sub = models.Subscription.transform(unit_price=s.unit_price,
                                                quantity=s.quantity,
                                                total_price=s.total_price,
                                                user_id=s.user_id,
                                                project_id=s.project_id,
                                                created_time=s.created_at)
            subscriptions.append(sub)

        return subscriptions


class SalesController(rest.RestController):
    """Sales information about all products
    """
    @wsexpose(models.Sales, wtypes.text, wtypes.text, wtypes.text,
              datetime.datetime, datetime.datetime)
    def get(self, name=None, service=None, region_id=None,
                start_time=None, end_time=None):
        """Get all products's statistics
        """
        filters = {}
        if name:
            filters.update(name=name)
        if service:
            filters.update(service=service)
        if region_id:
            filters.update(region_id=region_id)

        conn = pecan.request.db_conn

        # Get all products
        products = conn.get_products(request.context, filters=filters)

        total_price = gringutils._quantize_decimal(0)
        sales = []

        for p in products:
            total_price += p.total_price
            sales.append(models.Sale.transform(
                product_id=p.product_id,
                product_name=p.name,
                service=p.service,
                region_id=p.region_id,
                quantity=p.quantity,
                unit=p.unit,
                total_price=p.total_price))

        return models.Sales.transform(total_price=total_price,
                                      sales=sales,
                                      start_time=start_time,
                                      end_time=end_time)


class PriceController(rest.RestController):
    """Manages operations on the products collection
    """
    @wsexpose(models.Price, [models.Purchase])
    def get_all(self, purchases=[]):
        """Get price of a group of products
        """
        conn = pecan.request.db_conn

        unit_price = 0
        hourly_price = 0
        unit = None

        for p in purchases:
            if p.product_name and p.service and p.region_id and p.quantity:
                filters = dict(name=p.product_name,
                               service=p.service,
                               region_id=p.region_id)
                try:
                    product = list(conn.get_products(request.context,
                                                     filters=filters))[0]
                    hourly_price += product.unit_price * p.quantity
                    unit_price += product.unit_price
                    unit = product.unit
                except Exception as e:
                    LOG.error('Product %s not found' % p.product_name)
                    # NOTE(suo): Even through fail to find the product, we should't
                    # raise Exception, emit the price to zero.
                    #raise exception.ProductNameNotFound(product_name=p.product_name)
            else:
                raise exception.MissingRequiredParams()

        unit_price = gringutils._quantize_decimal(unit_price)
        hourly_price = gringutils._quantize_decimal(hourly_price)
        monthly_price = gringutils._quantize_decimal(hourly_price * 24 * 30)

        return models.Price.transform(unit_price=unit_price,
                                      hourly_price=hourly_price,
                                      monthly_price=monthly_price,
                                      unit=unit)


class DetailController(rest.RestController):
    """Detail of products
    """

    @wsexpose([models.Product], wtypes.text, wtypes.text, wtypes.text,
              int, wtypes.text, wtypes.text, wtypes.text)
    def get_all(self, name=None, service=None, region_id=None,
                limit=None, offset=None,
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
                                   offset=offset,
                                   sort_key=sort_key,
                                   sort_dir=sort_dir)
        return [models.Product.from_db_model(p) for p in result]


class ProductsController(rest.RestController):
    """Manages operations on the products collection
    """
    sales = SalesController()
    price = PriceController()
    detail = DetailController()

    @pecan.expose()
    def _lookup(self, product_id, *remainder):
        # drop last path if empty
        if remainder and not remainder[-1]:
            remainder = remainder[:-1]
        if uuidutils.is_uuid_like(product_id):
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

        product.unit_price = gringutils._quantize_decimal(product.unit_price)

        # DB model to API model
        return models.Product.from_db_model(product)

    @wsexpose([models.SimpleProduct], wtypes.text, wtypes.text, wtypes.text,
              int, wtypes.text, wtypes.text, wtypes.text)
    def get_all(self, name=None, service=None, region_id=None,
                limit=None, offset=None,
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
                                   offset=offset,
                                   sort_key=sort_key,
                                   sort_dir=sort_dir)
        return [models.SimpleProduct.transform(name=p.name,
                                               service=p.service,
                                               unit_price=p.unit_price,
                                               currency='CNY',
                                               unit=p.unit)
                for p in result]
