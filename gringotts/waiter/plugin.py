import abc
import copy

from oslo.config import cfg

from gringotts import context
from gringotts import db
from gringotts.db import models as db_models
from gringotts import exception
from gringotts import plugin

from gringotts.openstack.common import log
from gringotts.openstack.common import uuidutils


db_conn = db.get_connection(cfg.CONF)

LOG = log.getLogger(__name__)


class Collection(object):
    """Some field collection that ProductItem will use to get product or
    to create/update/delete subscription
    """
    def __init__(self, product_name, service, region_id, resource_id,
                 resource_name, resource_type, resource_volume,
                 user_id, project_id):
        self.product_name = product_name
        self.service = service
        self.region_id = region_id
        self.resource_id = resource_id
        self.resource_name = resource_name
        self.resource_type = resource_type
        self.resource_volume = resource_volume
        self.user_id = user_id
        self.project_id = project_id

    def as_dict(self):
        return copy.copy(self.__dict__)


class ProductItem(plugin.PluginBase):

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def get_collection(self, message):
        """Get collection from message
        """

    def _get_product(self, collection):
        """Get product from db
        """
        filters = dict(name=collection.product_name,
                       service=collection.service,
                       region_id=collection.region_id)

        result = list(db_conn.get_products(context.get_admin_context(),
                                           filters=filters))

        if len(result) > 1:
            msg = "Duplicated products with name(%s) within service(%s) in region_id(%s)" % \
                   (collection.product_name, collection.service, collection.region_id)
            LOG.error(msg)
            raise exception.DuplicatedProduct(reason=msg)

        if len(result) == 0:
            msg = "Product with name(%s) within service(%s) in region_id(%s) not found" % \
                   (collection.product_name, collection.service, collection.region_id)
            LOG.warning(msg)
            return None

        return result[0]

    def create_subscription(self, message, order_id, type=None):
        """Subscribe to this product
        """
        collection = self.get_collection(message)
        product = self._get_product(collection)

        # We don't bill the resource which can't find its products
        if not product:
            return None

        # Create subscription
        subscription_id = uuidutils.generate_uuid()
        product_id = product.product_id
        # copy unit price of the product to subscription
        unit_price = product.unit_price
        unit = product.unit
        quantity = collection.resource_volume
        total_price = 0
        user_id = collection.user_id
        project_id = collection.project_id

        subscription_in = db_models.Subscription(
            subscription_id, type, product_id, unit_price, unit,
            quantity, total_price, order_id, user_id, project_id)

        try:
            subscription = db_conn.create_subscription(context.get_admin_context(),
                                                       subscription_in)
        except Exception:
            LOG.exception('Fail to create subscription: %s' %
                          subscription_in.as_dict())
            raise exception.DBError(reason='Fail to create subscription')

        # Update product
        try:
            product = db_conn.get_product(context.get_admin_context(),
                                          product_id)
            product.quantity += quantity
            db_conn.update_product(context.get_admin_context(), product)
        except Exception:
            LOG.error("Fail to update the product\'s quantity: %s"
                      % subscription.as_dict())
            raise exception.DBError(reason='Fail to update the product')

        return subscription
