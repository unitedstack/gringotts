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


class RateLimitItem(waiter_plugin.ProductItem):

    def get_collection(self, message):
        """Get collection from message
        """
        product_name = const.PRODUCT_FLOATINGIP
        service = const.SERVICE_NETWORK
        region_id = cfg.CONF.region_name
        resource_id = message['payload']['floatingip']['id']
        resource_name = message['payload']['floatingip']['uos:name']
        resource_type = const.RESOURCE_FLOATINGIP
        resource_volume = int(message['payload']['floatingip']['rate_limit']) / 1024
        user_id = None
        project_id = message['payload']['floatingip']['tenant_id']

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
    namespace='gringotts.floatingip.product_item',
    invoke_on_load=True,
)


class FloatingIpNotificationBase(waiter_plugin.NotificationBase):
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

    def make_order(self, message, state=None):
        """Make an order model for one floating ip
        """
        resource_id = message['payload']['floatingip']['id']
        resource_name = message['payload']['floatingip']['uos:name']
        user_id = None
        project_id = message['payload']['floatingip']['tenant_id']

        order = Order(resource_id=resource_id,
                      resource_name=resource_name,
                      type=const.RESOURCE_FLOATINGIP,
                      status=state if state else const.STATE_RUNNING,
                      user_id=user_id,
                      project_id=project_id)
        return order


class FloatingIpCreateEnd(FloatingIpNotificationBase):
    """Handle the event that floating ip be created
    """
    event_types = ['floatingip.create.end']

    def process_notification(self, message, state=None):
        LOG.debug('Do action for event: %s, resource_id: %s',
                  message['event_type'],
                  message['payload']['floatingip']['id'])

        # Generate uuid of an order
        order_id = uuidutils.generate_uuid()

        unit_price = 0
        unit = None

        # Create subscriptions for this order
        for ext in product_items.extensions:
            if ext.name.startswith('suspend'):
                sub = ext.obj.create_subscription(message, order_id,
                                                  type=const.STATE_SUSPEND)
                if sub and state==const.STATE_SUSPEND:
                    p = gringutils._quantize_decimal(sub['unit_price'])
                    unit_price += p * sub['quantity']
                    unit = sub['unit']
            elif ext.name.startswith('running'):
                sub = ext.obj.create_subscription(message, order_id,
                                                  type=const.STATE_RUNNING)
                if sub and (not state or state==const.STATE_RUNNING):
                    p = gringutils._quantize_decimal(sub['unit_price'])
                    unit_price += p * sub['quantity']
                    unit = sub['unit']

        # Create an order for this instance
        self.create_order(order_id, unit_price, unit, message, state=state)

        # Notify master, just give master messages it needs
        remarks = 'Floating IP Has Been Created.'
        action_time = message['timestamp']
        if state:
            self.resource_created_again(order_id, action_time, remarks)
        else:
            self.resource_created(order_id, action_time, remarks)


class FloatingIpResizeEnd(FloatingIpNotificationBase):
    """Handle the events that floating ip be changed
    """
    event_types = ['floatingip.update_ratelimit.end']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s, resource_id: %s',
                  message['event_type'],
                  message['payload']['floatingip']['id'])

        quantity = int(message['payload']['floatingip']['rate_limit']) / 1024

        # Get the order of this resource
        resource_id = message['payload']['floatingip']['id']
        order = self.get_order_by_resource_id(resource_id)

        # Notify master
        action_time = message['timestamp']
        remarks = 'Floating IP Has Been Resized'
        self.resource_resized(order['order_id'], action_time, quantity, remarks)


class FloatingIpDeleteEnd(FloatingIpNotificationBase):
    """Handle the event that floating ip be deleted
    """
    event_types = ['floatingip.delete.end']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s, resource_id: %s',
                  message['event_type'],
                  message['payload']['floatingip_id'])

        # Get the order of this resource
        resource_id = message['payload']['floatingip_id']
        order = self.get_order_by_resource_id(resource_id)

        # Notify master
        action_time = message['timestamp']
        self.resource_deleted(order['order_id'], action_time)
