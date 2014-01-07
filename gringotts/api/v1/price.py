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


class PriceController(rest.RestController):
    """Manages operations on the products collection
    """
    @wsexpose(models.Price, [models.Purchase])
    def get_all(self, purchases=[]):
        """Get price of a group of products
        """
        conn = pecan.request.db_conn

        unit_price = 0
        hourly_amount = 0
        unit = None

        for p in purchases:
            if p.product_name and p.service and p.region_id and p.volume:
                filters = dict(name=p.product_name,
                              service=p.service,
                              region_id=p.region_id)
                try:
                    product = list(conn.get_products(request.context,
                                                     filters=filters))[0]
                    hourly_amount += product.unit_price * p.volume
                    unit_price += product.unit_price
                    unit = product.unit
                except Exception as e:
                    LOG.error('Product %s not found' % p.product_name)
                    # NOTE(suo): Even through fail to find the product, we should't
                    # raise Exception, emit the price to zero.
                    #raise exception.ProductNameNotFound(product_name=p.product_name)
            else:
                raise exception.MissingRequiredParams()

        return models.Price.transform(unit_price=unit_price,
                                      hourly_amount=round(hourly_amount, 4),
                                      monthly_amount=round(hourly_amount * 24 * 30, 4),
                                      unit=unit)
