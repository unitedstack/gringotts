import abc
import copy

from oslo.config import cfg

from gringotts import context
from gringotts import db
from gringotts import plugin
from gringotts import worker
from gringotts import master

from gringotts.openstack.common import log


db_conn = db.get_connection(cfg.CONF)

LOG = log.getLogger(__name__)

worker_api = worker.API()
master_api = master.API()


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

    def create_subscription(self, message, order_id, type=None):
        """Subscribe to this product
        """
        collection = self.get_collection(message)

        LOG.debug('Create subscription for order: %s' % order_id)

        result = worker_api.create_subscription(context.get_admin_context(),
                                                order_id,
                                                type=type,
                                                **collection.as_dict())
        return result


class Order(object):
    """Some field collection that ProductItem will use to get product or
    to create/update/delete subscription
    """
    def __init__(self, resource_id, resource_name, user_id, project_id,
                 type, status):
        self.resource_id = resource_id
        self.resource_name = resource_name
        self.user_id = user_id
        self.project_id = project_id
        self.type = type
        self.status = status

    def as_dict(self):
        return copy.copy(self.__dict__)


class NotificationBase(plugin.NotificationBase):

    @abc.abstractmethod
    def make_order(self, message):
        """Collect distinct fileds from different plugins
        """

    def create_order(self, order_id, unit_price, unit, message):
        """Create an order for resource created
        """
        order = self.make_order(message)

        LOG.debug('Create order for order_id: %s' % order_id)

        worker_api.create_order(context.get_admin_context(),
                                order_id,
                                cfg.CONF.region_name,
                                unit_price,
                                unit,
                                **order.as_dict())

    def get_order_by_resource_id(self, resource_id):
        return worker_api.get_order_by_resource_id(context.get_admin_context(),
                                                   resource_id)

    def resource_created(self, order_id, action_time, remarks):
        """Notify master that resource has been created
        """
        master_api.resource_created(context.get_admin_context(),
                                    order_id,
                                    action_time, remarks)

    def resource_deleted(self, order_id, action_time):
        """Notify master that resource has been deleted
        """
        master_api.resource_deleted(context.get_admin_context(),
                                    order_id,
                                    action_time)

    def resource_resized(self, order_id, action_time, quantity, remarks):
        """Notify master that resource has been resized
        """
        master_api.resource_resized(context.get_admin_context(),
                                    order_id,
                                    action_time, quantity, remarks)

    def resource_changed(self, order_id, action_time, change_to, remarks):
        """Notify master that resource has been changed
        """
        master_api.resource_changed(context.get_admin_context(),
                                    order_id,
                                    action_time, change_to, remarks)
