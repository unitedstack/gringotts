#!/usr/bin/python
"""Plugins for executing specific actions acrronding to notification events.
"""
from oslo.config import cfg
from stevedore import extension

from gringotts import constants as const
from gringotts import utils as gringutils
from gringotts import plugin
from gringotts.waiter import plugin as waiter_plugin
from gringotts.waiter.plugin import Collection
from gringotts.waiter.plugin import Order

from gringotts.openstack.common import log
from gringotts.openstack.common import uuidutils


LOG = log.getLogger(__name__)


OPTS = [
    cfg.StrOpt('neutron_control_exchange',
               default='neutron',
               help="Exchange name for Neutron notifications"),
]


cfg.CONF.register_opts(OPTS)


class RouterItem(waiter_plugin.ProductItem):

    def get_collection(self, message):
        """Get collection from message
        """
        product_name = const.PRODUCT_ROUTER
        service = const.SERVICE_NETWORK
        region_id = cfg.CONF.region_name
        resource_id = message['payload']['router']['id']
        resource_name = message['payload']['router']['name']
        resource_type = const.RESOURCE_ROUTER
        resource_volume = 1
        user_id = None
        project_id = message['payload']['router']['tenant_id']

        return Collection(product_name=product_name,
                          service=service,
                          region_id=region_id,
                          resource_id=resource_id,
                          resource_name=resource_name,
                          resource_type=resource_type,
                          resource_volume=resource_volume,
                          user_id=user_id,
                          project_id=project_id)


product_items = extension.ExtensionManager(
    namespace='gringotts.router.product_item',
    invoke_on_load=True,
)


class RouterNotificationBase(waiter_plugin.NotificationBase):
    @staticmethod
    def get_exchange_topics(conf):
        """Return a sequence of ExchangeTopics defining the exchange and
        topics to be connected for this plugin.
        """
        return [
            plugin.ExchangeTopics(
                exchange=conf.neutron_control_exchange,
                topics=set(topic + ".info"
                           for topic in conf.notification_topics)),
        ]

    def make_order(self, message):
        """Make an order model for one router
        """
        resource_id = message['payload']['router']['id']
        resource_name = message['payload']['router']['name']
        user_id = None
        project_id = message['payload']['router']['tenant_id']

        order = Order(resource_id=resource_id,
                      resource_name=resource_name,
                      type=const.RESOURCE_ROUTER,
                      status=const.STATE_RUNNING,
                      user_id=user_id,
                      project_id=project_id)
        return order


class RouterCreateEnd(RouterNotificationBase):
    """Handle the event that router be created
    """
    event_types = ['router.create.end']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s, resource_id: %s',
                  message['event_type'], message['payload']['router']['id'])

        # Generate uuid of an order
        order_id = uuidutils.generate_uuid()

        unit_price = 0
        unit = None

        # Create subscriptions for this order
        for ext in product_items.extensions:
            if ext.name.startswith('suspend'):
                ext.obj.create_subscription(message, order_id,
                                            type=const.STATE_SUSPEND)
            elif ext.name.startswith('running'):
                sub = ext.obj.create_subscription(message, order_id,
                                                  type=const.STATE_RUNNING)
                if sub:
                    p = gringutils._quantize_decimal(sub['unit_price'])
                    unit_price += p * sub['quantity']
                    unit = sub['unit']

        # Create an order for this router
        self.create_order(order_id, unit_price, unit, message)

        # Notify master
        remarks = 'Router Has Been Created.'
        action_time = message['timestamp']
        self.resource_created(order_id, action_time, remarks)


class RouterDeleteEnd(RouterNotificationBase):
    """Handle the event that router be deleted
    """
    event_types = ['router.delete.end']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s, resource_id: %s',
                  message['event_type'], message['payload']['router_id'])

        # Get the order of this resource
        resource_id = message['payload']['router_id']
        order = self.get_order_by_resource_id(resource_id)

        # Notify master
        action_time = message['timestamp']
        self.resource_deleted(order['order_id'], action_time)
