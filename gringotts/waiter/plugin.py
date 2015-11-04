import abc
import copy

from oslo.config import cfg

from gringotts.client import client
from gringotts import context
from gringotts import constants as const
from gringotts import db
from gringotts import master
from gringotts.openstack.common import log
from gringotts import plugin
from gringotts.price import pricing
from gringotts import utils as gringutils


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
        self.gclient = client.get_client()

    @abc.abstractmethod
    def get_collection(self, message):
        """Get collection from message
        """

    def create_subscription(self, message, order_id, type=None):
        """Subscribe to this product
        """
        collection = self.get_collection(message)

        LOG.debug('Create subscription for order: %s' % order_id)

        result = self.gclient.create_subscription(order_id,
                                                  type=type,
                                                  **collection.as_dict())
        return result

    def get_unit_price(self, order_id, message):
        """Get unit price of this resource

        As the resource has subscribed to the product, so we should
        calculate price from the subscriptions instead of the product.
        """
        c = self.get_collection(message)
        product = self.gclient.get_product(
            c.product_name, c.service, c.region_id)

        if not product:
            return 0

        subs = self.gclient.get_subscriptions(order_id,
                                              product_id=product['product_id'])
        if subs:
            sub = subs[0]
        else:
            LOG.warn("The order %s has no subscriptions" % order_id)
            return 0

        if 'extra' in sub:
            price_data = pricing.get_price_data(sub['extra'])
        else:
            price_data = None

        return pricing.calculate_price(
            c.resource_volume, sub['unit_price'], price_data)


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
        self.gclient = client.get_client()
        self.master_api = master.API()

    @abc.abstractmethod
    def make_order(self, message, state=None):
        """Collect distinct fileds from different plugins
        """

    def get_unit_price(self, order_id, message, status, cron_time=None):
        return

    def change_unit_price(self, message, status, order_id):
        return

    def change_order_unit_price(self, order_id, quantity, status):
        """Change the order's subscriptions and unit price"""
        # change subscirption's quantity
        self.gclient.change_subscription(order_id, quantity, status)

        # change the order's unit price
        self.gclient.change_order(order_id, status)

    def change_flavor_unit_price(self, order_id, new_flavor,
                                 service, region_id, status):
        """Change the order's flavor subscription and unit price"""
        if status == const.STATE_RUNNING:
            # change subscirption's quantity
            self.gclient.change_flavor_subscription(order_id,
                                                    new_flavor, None,
                                                    service, region_id,
                                                    const.STATE_RUNNING)

        # change the order's unit price
        self.gclient.change_order(order_id, status)

    def create_order(self, order_id, unit_price, unit, message, state=None):
        """Create an order for resource created
        """
        order = self.make_order(message, state=state)

        LOG.debug('Create order for order_id: %s' % order_id)

        self.gclient.create_order(order_id,
                                  cfg.CONF.region_name,
                                  unit_price,
                                  unit,
                                  **order.as_dict())

    def get_order_by_resource_id(self, resource_id):
        return self.gclient.get_order_by_resource_id(resource_id)

    def create_account(self, user_id, domain_id, balance, consumption, level,
                       **kwargs):
        self.gclient.create_account(user_id, domain_id, balance,
                                    consumption, level, **kwargs)

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
        self.gclient.change_flavor_subscription(order_id,
                                                new_flavor, old_flavor,
                                                service, region_id,
                                                const.STATE_RUNNING)

    def charge_account(self, user_id, value, type, come_from):
        """Charge the account
        """
        self.gclient.charge_account(user_id, value, type, come_from)

    def create_project(self, user_id, project_id, domain_id, consumption):
        """Create a project whose project owner is user_id
        """
        self.gclient.create_project(user_id, project_id, domain_id, consumption)

    def delete_resources(self, project_id):
        """Delete all resources of project"""
        self.gclient.delete_resources(project_id)

    def change_billing_owner(self, project_id, user_id):
        """Change billing owner"""
        self.gclient.change_billing_owner(project_id, user_id)

    def get_subscriptions(self, order_id=None, type=None):
        """Get subscription of specific order"""
        return self.gclient.get_subscriptions(order_id=order_id, type=type)
