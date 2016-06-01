# -*- coding: utf-8 -*-

import datetime
import json

from oslo_config import cfg
import pecan
from pecan import rest
from pecan import request
from wsme import types as wtypes
from wsmeext.pecan import wsexpose

from gringotts.api.v2 import models
from gringotts.db import models as db_models
from gringotts import exception
from gringotts.openstack.common import jsonutils
from gringotts.openstack.common import log
from gringotts.openstack.common import uuidutils
from gringotts.price import pricing
from gringotts import utils as gringutils

LOG = log.getLogger(__name__)


quantize_decimal = gringutils._quantize_decimal


class ProductExtraData(object):

    def __init__(self, extra_json_string):
        try:
            self.extra = json.loads(extra_json_string)
        except (Exception) as e:
            err = 'Extra data is not a valid JSON string, %s' % (e)
            LOG.warning(err)
            raise exception.InvalidParameterValue(err=err)

        self.new_extra = {}

    def validate(self):
        try:
            for key in ['price', 'monthly_price', 'yearly_price']:
                if key in self.extra:
                    self.new_extra[key] = pricing.validate_price_data(
                        self.extra[key])
        except (exception.GringottsException) as e:
            LOG.warning(e.format_message())
            raise e

        return json.dumps(self.new_extra)


class ProductController(rest.RestController):
    """Manages operations on a single product."""

    def __init__(self, product_id):
        pecan.request.context['product_id'] = product_id
        self._id = product_id

    def _product(self):
        self.conn = pecan.request.db_conn
        try:
            product = self.conn.get_product(request.context,
                                            product_id=self._id)
        except Exception:
            LOG.error('Product %s not found' % self._id)
            raise exception.ProductIdNotFound(product_id=self._id)
        return product

    @wsexpose(models.Product, wtypes.text)
    def get(self):
        """Return this product."""
        return models.Product.from_db_model(self._product())

    @wsexpose(None, wtypes.text, status_code=204)
    def delete(self):
        """Delete this product."""
        # ensure product exists before deleting
        product = self._product()
        try:
            self.conn.delete_product(request.context, product.product_id)
        except Exception:
            error = 'Error while deleting product: %s' % product.product_id
            LOG.exception(error)
            raise exception.DBError(reason=error)

    @wsexpose(models.Product, wtypes.text, body=models.Product)
    def put(self, data):
        """Modify this product. PUT method will override all the fields."""
        # Ensure this product exists
        # NOTE(suo): we can't make product_in and product_old
        # point to the same object
        product_in = self._product()
        product_old = self._product()

        p = data.as_dict()

        # Default to reset subscription and order
        reset = p.pop("reset") if 'reset' in p else True

        for k, v in p.items():
            product_in[k] = v

        product_in.updated_at = datetime.datetime.utcnow()

        # Check and process extra data
        if product_in.unit_price is not None:
            price_data = ProductExtraData(product_in.unit_price)
            new_price_data = price_data.validate()
            product_in.unit_price = new_price_data

        # Check if there are other same names in the same region
        # except itself
        filters = {'name': product_in.name,
                   'service': product_in.service,
                   'region_id': product_in.region_id}
        products = list(self.conn.get_products(
            request.context, filters=filters))

        if len(products) > 0 and (
                (product_old.name != product_in.name) or (
                    product_old.service != product_in.service) or (
                        product_old.region_id != product_in.region_id)):
            error = "Product with name(%s) within service(%s) already "\
                    "exists in region_id(%s)" % \
                    (data.name, data.service, data.region_id)
            LOG.warning(error)
            raise exception.DuplicatedProduct(reason=error)

        # Update product model to DB
        try:
            product = self.conn.update_product(request.context, product_in)
        except Exception:
            error = 'Error while updating product: %s' % data.as_dict()
            LOG.exception(error)
            raise exception.DBError(reason=error)

        # Reset order and subscription's unit price
        if reset:
            try:
                self.conn.reset_product(
                    request.context, product, cfg.CONF.ignore_tenants)
            except Exception:
                error = "Fail to reset the product: %s" % data.as_dict()
                LOG.exception(error)
                raise exception.DBError(reason=error)

        # DB model to API model
        return models.Product.from_db_model(product)


class PriceController(rest.RestController):
    """Process price of product."""

    @wsexpose(models.Price, models.Purchase)
    def get_all(self, purchase):
        """Get price of a group of products."""

        if purchase.bill_method not in ['hour', 'month', 'year']:
            err = 'Should specify bill_method among hour, month and year'
            raise exception.InvalidParameterValue(err=err)

        if not isinstance(purchase.bill_period, int):
            purchase.bill_period = 1

        conn = pecan.request.db_conn

        unit_price = quantize_decimal(0)
        unit = purchase.bill_method

        for p in purchase.purchases:
            if all([p.product_id, p.quantity]):
                try:
                    product = conn.get_product(request.context, p.product_id)
                except exception.ProductIdNotFound:
                    LOG.warn("Product %s not found" % p.product_id)
                    raise
            elif all([p.product_name, p.service, p.region_id, p.quantity]):
                filters = dict(name=p.product_name,
                               service=p.service,
                               region_id=p.region_id)
                products = list(conn.get_products(
                    request.context, filters=filters))
                if len(products) == 0:
                    LOG.error('Product %s of region %s not found',
                              p.product_name, p.region_id)
                    raise exception.ProductNameNotFound(
                        product_name=p.product_name)
                product = products[0]
            else:
                err = "Every purchase item should specify product_name, "\
                      "service, region_id and quantity or "\
                      "product_id and quantity."
                raise exception.MissingRequiredParams(reason=err)
            try:
                if product.unit_price:
                    price_data = pricing.get_price_data(product.unit_price,
                                                        unit)
                else:
                    price_data = None

                unit_price += pricing.calculate_price(
                    p.quantity, price_data)
            except (Exception) as e:
                LOG.error('Calculate price of product %s failed, %s',
                          p.product_name, e)
                raise e
        total_price = unit_price * purchase.bill_period
        return models.Price.transform(unit_price=unit_price,
                                      unit=unit,
                                      total_price=total_price)


class DetailController(rest.RestController):
    """Detail of products."""

    @wsexpose(models.Products, wtypes.text, wtypes.text, wtypes.text,
              int, int, wtypes.text, wtypes.text)
    def get_all(self, name=None, service=None, region_id=None,
                limit=None, offset=None,
                sort_key='created_at', sort_dir='desc'):
        """Get all product."""

        if limit and limit < 0:
            raise exception.InvalidParameterValue(err="Invalid limit")
        if offset and offset < 0:
            raise exception.InvalidParameterValue(err="Invalid offset")

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
        products = [models.Product.from_db_model(p) for p in result]
        total_count = conn.get_products_count(request.context,
                                              filters=filters)
        return models.Products(total_count=total_count,
                               products=products)


class ProductsController(rest.RestController):
    """Manages operations on the products collection."""

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
        """Create a new product."""
        data.product_id = uuidutils.generate_uuid()
        conn = pecan.request.db_conn

        # API model to DB model
        try:
            product_in = db_models.Product(quantity=0,
                                           deleted=False,
                                           **data.as_dict())
        except Exception:
            error = 'Error while turning product: %s' % data.as_dict()
            LOG.exception(error)
            raise exception.MissingRequiredParams(reason=error)

        # Check and process extra data
        if product_in.unit_price is not None:
            price_data = ProductExtraData(product_in.unit_price)
            new_price_data = price_data.validate()
            product_in.unit_price = new_price_data

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
        except Exception:
            error = 'Error while creating product: %s' % data.as_dict()
            LOG.exception(error)
            raise exception.DBError(reason=error)

        product.unit_price = quantize_decimal(product.unit_price)

        # DB model to API model
        return models.Product.from_db_model(product)

    @wsexpose([models.SimpleProduct], wtypes.text, wtypes.text, wtypes.text,
              int, int, wtypes.text, wtypes.text)
    def get_all(self, name=None, service=None, region_id=None,
                limit=None, offset=None,
                sort_key='created_at', sort_dir='desc'):
        """Get all product."""

        if limit and limit < 0:
            raise exception.InvalidParameterValue(err="Invalid limit")
        if offset and offset < 0:
            raise exception.InvalidParameterValue(err="Invalid offset")

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
                                               region_id=p.region_id,
                                               product_id=p.product_id,
                                               unit_price=p.unit_price,
                                               currency='CNY')
                for p in result]
