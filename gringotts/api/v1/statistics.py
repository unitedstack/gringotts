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
    """Statistics for a single product
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

    @wsexpose(models.ProductStatisticsDetail, wtypes.text,
              datetime.datetime, datetime.datetime,
              int, wtypes.text, wtypes.text, wtypes.text)
    def get(self, start_time=None, end_time=None,
            limit=None, marker=None, sort_key='id', sort_dir='asc'):
        """Return this product's subscriptions"""
        product = self._product()

        subs = self.conn.get_subscriptions_by_product_id(request.context,
                                                         self._id,
                                                         start_time=start_time,
                                                         end_time=end_time,
                                                         limit=limit,
                                                         marker=marker,
                                                         sort_key=sort_key,
                                                         sort_dir=sort_dir)
        total_sales = 0
        total_volume = 0
        statistics = []
        for s in subs:
            sub = models.ProductSubscription.transform(resource_id=s.resource_id,
                                                       resource_name=s.resource_name,
                                                       resource_volume=s.resource_volume,
                                                       user_id=s.user_id,
                                                       project_id=s.project_id,
                                                       sales=s.current_fee,
                                                       created_time=s.created_at)
            statistics.append(sub)

            total_sales += s.current_fee
            total_volume += s.resource_volume

        return models.ProductStatisticsDetail.transform(
            product_id=self._id,
            product_name=product.name,
            service=product.service,
            region_id=product.region_id,
            total_sales=total_sales,
            total_volume=total_volume,
            subscriptions=statistics,
            start_time=start_time,
            end_time=end_time)


class ProductsController(rest.RestController):
    """Statistics for all products
    """
    @pecan.expose()
    def _lookup(self, product_id, *remainder):
        if remainder and not remainder[-1]:
            remainder = remainder[:-1]
        return ProductController(product_id), remainder

    @wsexpose(models.ProductsStatistics, wtypes.text, wtypes.text, wtypes.text,
              datetime.datetime, datetime.datetime,
              int, wtypes.text, wtypes.text, wtypes.text)
    def get_all(self, name=None, service=None, region_id=None,
                start_time=None, end_time=None,
                limit=None, marker=None, sort_key='id', sort_dir='asc'):
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
        result = conn.get_products(request.context,
                                   filters=filters,
                                   limit=limit,
                                   marker=marker,
                                   sort_key=sort_key,
                                   sort_dir=sort_dir)

        # Get all subscriptions of every product
        total_sales = 0
        statistics = []
        for p in result:
            subs = conn.get_subscriptions_by_product_id(request.context,
                                                        p.product_id,
                                                        start_time=start_time,
                                                        end_time=end_time)
            sales = 0
            volume = 0

            for s in subs:
                sales += s.current_fee
                volume += s.resource_volume

            statistics.append(models.ProductStatistics.transform(
                product_id=p.product_id,
                product_name=p.name,
                service=p.service,
                region_id=p.region_id,
                volume=volume,
                unit=p.unit,
                sales=sales))
            total_sales += sales

        return models.ProductsStatistics.transform(total_sales=total_sales,
                                                   products=statistics,
                                                   start_time=start_time,
                                                   end_time=end_time)


class ResourceController(rest.RestController):
    """For one single resource
    """
    def __init__(self, resource_id):
        self._id = resource_id

    @wsexpose(models.ResourceStatisticsDetail, wtypes.text,
              datetime.datetime, datetime.datetime,
              int, wtypes.text, wtypes.text, wtypes.text)
    def get(self, start_time=None, end_time=None,
            limit=None, marker=None, sort_key='id', sort_dir='asc'):
        """Return this product's subscriptions
        """
        return models.ResourceStatisticsDetail.sample()


class ResourcesController(rest.RestController):
    """The controller of resources
    """
    @pecan.expose()
    def _lookup(self, resource_id, *remainder):
        if remainder and not remainder[-1]:
            remainder = remainder[:-1]
        return ResourceController(resource_id), remainder

    @wsexpose(models.ResourcesStatistics, wtypes.text,
              datetime.datetime, datetime.datetime,
              int, wtypes.text, wtypes.text, wtypes.text)
    def get_all(self, resource_type=None, start_time=None, end_time=None,
                limit=None, marker=None, sort_key='id', sort_dir='asc'):
        """Get subscriptions group by resource_id
        """
        conn = pecan.request.db_conn

        # Get all resources from subscription table, filter by project_id,
        # and group by resource_id
        resources = conn.get_subscriptions_group_by_resource_id(request.context,
                resource_type=resource_type, start_time=start_time,
                end_time=end_time, limit=limit, marker=marker, sort_key=sort_key,
                sort_dir=sort_dir)

        resources_list = []
        resources_total_price = 0
        resource_amount = 0

        # Caculate every resource's consumption
        for resource in resources:
            resource_amount += 1
            resource_total_price = 0

            subs = conn.get_subscriptions_by_resource_id(request.context,
                    resource.resource_id)

            for sub in subs:
                resource_total_price += sub.current_fee

            resources_total_price += resource_total_price

            resources_list.append(models.ResourceStatistics(
                resource_id=resource.resource_id,
                resource_name=resource.resource_name,
                resource_status=resource.resource_status,
                resource_volume=resource.resource_volume,
                total_price=resource_total_price,
                created_time=resource.created_at))

        return models.ResourcesStatistics(
                total_price=resources_total_price,
                resource_amount=resource_amount,
                resources=resources_list,
                resource_type=resource_type)


class StatisticsController(rest.RestController):
    """Aggregate all aspect of product, subscription, bill to statistics
    """
    products = ProductsController()
    resources = ResourcesController()
