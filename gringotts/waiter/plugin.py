import abc
import copy

from oslo.config import cfg

from gringotts import utils as gringutils
from gringotts import constants as const
from gringotts import context
from gringotts import db
from gringotts import plugin
from gringotts import worker
from gringotts import master

from gringotts.openstack.common import log


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

    def __init__(self):
        self.worker_api = worker.API()

    @abc.abstractmethod
    def get_collection(self, message):
        """Get collection from message
        """

    def create_subscription(self, message, order_id, type=None):
        """Subscribe to this product
        """
        collection = self.get_collection(message)

        LOG.debug('Create subscription for order: %s' % order_id)

        result = self.worker_api.create_subscription(context.get_admin_context(),
                                                     order_id,
                                                     type=type,
                                                     **collection.as_dict())
        return result

    def get_unit_price(self, message):
        """Get product unit price"""
        collection = self.get_collection(message)
        product = self.worker_api.get_product(context.get_admin_context(),
                                              collection.product_name,
                                              collection.service,
                                              collection.region_id)
        if product:
            return collection.resource_volume * gringutils._quantize_decimal(product['unit_price'])
        return 0


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

    def __init__(self):
        self.worker_api = worker.API()
        self.master_api = master.API()

    @abc.abstractmethod
    def make_order(self, message, state=None):
        """Collect distinct fileds from different plugins
        """

    def get_unit_price(self, message, status, cron_time=None):
        return

    def change_unit_price(self, message, status, order_id):
        return

    def change_order_unit_price(self, order_id, quantity, status):
        """Change the order's subscriptions and unit price"""
        # change subscirption's quantity
        self.worker_api.change_subscription(context.get_admin_context(),
                                            order_id, quantity, status)

        # change the order's unit price
        self.worker_api.change_order(context.get_admin_context(), order_id, status)

    def change_flavor_unit_price(self, order_id, new_flavor, service, region_id, status):
        """Change the order's flavor subscription and unit price"""
        if status == const.STATE_RUNNING:
            # change subscirption's quantity
            self.worker_api.change_flavor_subscription(context.get_admin_context(),
                                                       order_id,
                                                       new_flavor, None,
                                                       service, region_id,
                                                       const.STATE_RUNNING)

        # change the order's unit price
        self.worker_api.change_order(context.get_admin_context(), order_id, status)

    def create_order(self, order_id, unit_price, unit, message, state=None):
        """Create an order for resource created
        """
        order = self.make_order(message, state=state)

        LOG.debug('Create order for order_id: %s' % order_id)

        self.worker_api.create_order(context.get_admin_context(),
                                     order_id,
                                     cfg.CONF.region_name,
                                     unit_price,
                                     unit,
                                     **order.as_dict())

    def get_order_by_resource_id(self, resource_id):
        return self.worker_api.get_order_by_resource_id(context.get_admin_context(),
                                                        resource_id)

    def create_account(self, user_id, domain_id, balance, consumption, level,
                       **kwargs):
        self.worker_api.create_account(context.get_admin_context(),
                                       user_id, domain_id, balance, consumption, level,
                                       **kwargs)

    def resource_created(self, order_id, action_time, remarks):
        """Notify master that resource has been created
        """
        self.master_api.resource_created(context.get_admin_context(),
                                         order_id,
                                         action_time, remarks)

    def resource_created_again(self, order_id, action_time, remarks):
        """Notify master that resource has been created
        """
        self.master_api.resource_created_again(context.get_admin_context(),
                                               order_id,
                                               action_time, remarks)

    def resource_started(self, order_id, action_time, remarks):
        """Notify master that resource has been started
        """
        self.master_api.resource_started(context.get_admin_context(),
                                         order_id,
                                         action_time,
                                         remarks)

    def resource_stopped(self, order_id, action_time, remarks):
        """Notify master that resource has been stopped
        """
        self.master_api.resource_stopped(context.get_admin_context(),
                                         order_id,
                                         action_time,
                                         remarks)

    def resource_deleted(self, order_id, action_time, remarks):
        """Notify master that resource has been deleted
        """
        self.master_api.resource_deleted(context.get_admin_context(),
                                         order_id,
                                         action_time,
                                         remarks)

    def resource_resized(self, order_id, action_time, quantity, remarks):
        """Notify master that resource has been resized
        """
        self.master_api.resource_resized(context.get_admin_context(),
                                         order_id,
                                         action_time, quantity, remarks)

    def resource_changed(self, order_id, action_time, change_to, remarks):
        """Notify master that resource has been changed
        """
        self.master_api.resource_changed(context.get_admin_context(),
                                         order_id,
                                         action_time, change_to, remarks)

    def instance_stopped(self, order_id, action_time):
        """Notify master that instance has been stopped
        """
        self.master_api.instance_stopped(context.get_admin_context(),
                                         order_id, action_time)

    def instance_resized(self, order_id, action_time,
                         new_flavor, old_flavor, service, region_id,
                         remarks):
        """Notify master that instance has been resized
        """
        # change subscirption's product
        self.worker_api.change_flavor_subscription(context.get_admin_context(),
                                                   order_id,
                                                   new_flavor, old_flavor,
                                                   service, region_id,
                                                   const.STATE_RUNNING)

    def charge_account(self, user_id, value, type, come_from):
        """Charge the account
        """
        self.worker_api.charge_account(context.get_admin_context(),
                                       user_id, value, type, come_from)

    def create_project(self, user_id, project_id, domain_id, consumption):
        """Create a project whose project owner is user_id
        """
        self.worker_api.create_project(context.get_admin_context(),
                                       user_id, project_id, domain_id, consumption)

    def delete_resources(self, project_id):
        """Delete all resources of project"""
        self.worker_api.delete_resources(context.get_admin_context(), project_id)

    def change_billing_owner(self, project_id, user_id):
        """Change billing owner"""
        self.worker_api.change_billing_owner(context.get_admin_context(), project_id, user_id)
