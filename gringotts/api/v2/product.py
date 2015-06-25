# -*- coding: utf-8 -*-

import pecan
import datetime
import collections
import json

from pecan import rest
from pecan import request
from wsmeext.pecan import wsexpose
from wsme import types as wtypes

from oslo.config import cfg

from gringotts import exception
from gringotts import utils as gringutils

from gringotts.api.v2 import models
from gringotts.db import models as db_models
from gringotts.openstack.common import log
from gringotts.openstack.common import uuidutils


LOG = log.getLogger(__name__)


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
            if 'price' in self.extra:
                self._validate_price()
        except (exception.GringottsException) as e:
            LOG.warning(e.format_message())
            raise e

        return json.dumps(self.new_extra)

    def _validate_price(self):
        price_data = self.extra['price']
        if 'type' not in price_data:
            raise exception.InvalidParameterValue(
                err='Invalid price type')

        new_price_data = {'type': price_data['type']}
        if price_data['type'] == 'segmented':
            new_price_data['segmented'] = \
                self._validate_segmented_price(price_data)

        # Validate value of 'base_price'
        if 'base_price' not in price_data:
            new_price_data['base_price'] = 0
        else:
            base_price = price_data['base_price']
            if not isinstance(base_price, (int, float)):
                raise exception.InvalidParameterValue(
                    err='Invalid base price type')
            if base_price < 0:
                raise exception.InvalidParameterValue(
                    err='Base price should not be negative')
            new_price_data['base_price'] = base_price

        self.new_extra['price'] = new_price_data

    def _validate_segmented_price(self, price_data):
        if ('segmented' not in price_data) \
                or (not isinstance(price_data['segmented'], list)):
            raise exception.InvalidParameterValue(
                err='No segmented price list in price data')

        price_list = price_data['segmented']

        # check if item in price_list is valid
        # valid price item is of the form:
        #     [(quantity_level)int, (unit_price)int/float]
        item_is_valid = all(
            (len(p) == 2
             and isinstance(p[0], int)
             and isinstance(p[1], (int, float))
             and p[1] >= 0
             )
            for p in price_list
        )
        if not item_is_valid:
            raise exception.InvalidParameterValue(
                err='Segmented price list has invalid price item')

        # check if price list has duplicate items
        c = collections.Counter([p[0] for p in price_list])
        has_duplicate_items = any([v[1] != 1 for v in c.items()])
        if has_duplicate_items:
            raise exception.InvalidParameterValue(
                err='Segmented price list has duplicate items')

        # sort price list
        sorted_price_list = sorted(
            price_list, key=lambda p: p[0], reverse=True)

        # check the price list start from 0
        if sorted_price_list[-1][0] != 0:
            raise exception.InvalidParameterValue(
                err='Number of resource should start from 0')

        return sorted_price_list


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
        except Exception:
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
        except Exception:
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

        p = data.as_dict()

        # Default to reset subscription and order
        reset = p.pop("reset") if 'reset' in p else True

        for k, v in p.items():
            product_in[k] = v

        product_in.updated_at = datetime.datetime.utcnow()

        # Check and process extra data
        if product_in.extra is not None:
            extra_data = ProductExtraData(product_in.extra)
            new_extra_data = extra_data.validate()
            product_in.extra = new_extra_data

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
        except Exception:
            error = 'Error while updating product: %s' % data.as_dict()
            LOG.exception(error)
            raise exception.DBError(reason=error)

        # Reset order and subscription's unit price
        if reset:
            try:
                self.conn.reset_product(request.context, product, cfg.CONF.ignore_tenants)
            except Exception:
                error = "Fail to reset the product: %s" % data.as_dict()
                LOG.exception(error)
                raise exception.DBError(reason=error)

        # DB model to API model
        return models.Product.from_db_model(product)


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
                except Exception:
                    LOG.error('Product %s not found' % p.product_name)
                    # NOTE(suo): Even through fail to find the product, we should't
                    # raise Exception, emit the price to zero.
                    # raise exception.ProductNameNotFound(product_name=p.product_name)
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

    @wsexpose(models.Products, wtypes.text, wtypes.text, wtypes.text,
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
        products = [models.Product.from_db_model(p) for p in result]
        total_count = conn.get_products_count(request.context,
                                              filters=filters)
        return models.Products(total_count=total_count,
                               products=products)


class ProductsController(rest.RestController):
    """Manages operations on the products collection
    """
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
                                           deleted=False,
                                           **data.as_dict())
        except Exception:
            error = 'Error while turning product: %s' % data.as_dict()
            LOG.exception(error)
            raise exception.MissingRequiredParams(reason=error)

        # Check and process extra data
        if product_in.extra is not None:
            extra_data = ProductExtraData(product_in.extra)
            new_extra_data = extra_data.validate()
            product_in.extra = new_extra_data

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
                                               unit=p.unit,
                                               extra=p.extra)
                for p in result]
