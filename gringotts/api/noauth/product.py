import pecan
import wsme

from pecan import rest
from pecan import request
from wsmeext.pecan import wsexpose
from wsme import types as wtypes

from oslo_config import cfg

from gringotts.api.v2 import models
from gringotts.db import models as db_models
from gringotts.openstack.common import log


LOG = log.getLogger(__name__)


class ProductsController(rest.RestController):
    """Manages operations on the products collection
    """

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
