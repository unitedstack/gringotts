#!/usr/bin/python
"""Plugins for executing specific actions acrronding to notification events.
"""
from oslo_config import cfg
from stevedore import extension

from gringotts import constants as const
from gringotts import utils as gringutils
from gringotts import plugin
from gringotts.waiter import plugin as waiter_plugin
from gringotts.waiter.plugin import Collection
from gringotts.waiter.plugin import Order

from gringotts import services
from gringotts.services import keystone as ks_client

from gringotts.openstack.common import log
from gringotts.openstack.common import uuidutils


LOG = log.getLogger(__name__)


OPTS = [
    cfg.StrOpt('neutron_control_exchange',
               default='neutron',
               help="Exchange name for Neutron notifications"),
]


cfg.CONF.register_opts(OPTS)


class ConnectionLimitItem(waiter_plugin.ProductItem):

    def get_collection(self, message):
        """Get collection from message
        """
        product_name = const.PRODUCT_LISTENER
        service = const.SERVICE_NETWORK
        region_id = cfg.CONF.region_name
        resource_id = message['payload']['listener']['id']
        resource_name = message['payload']['listener']['name']
        resource_type = const.RESOURCE_LISTENER
        resource_volume = int(message['payload']['listener']['connection_limit']) / 1000
        user_id = None
        project_id = message['payload']['listener']['tenant_id']

        return Collection(product_name=product_name,
                          service=service,
                          region_id=region_id,
                          resource_id=resource_id,
                          resource_name=resource_name,
                          resource_type=resource_type,
                          resource_volume=resource_volume,
                          user_id=user_id,
                          project_id=project_id)


class ListenerNotificationBase(waiter_plugin.NotificationBase):

    def __init__(self):
        super(ListenerNotificationBase, self).__init__()
        self.product_items = extension.ExtensionManager(
            namespace='gringotts.listener.product_item',
            invoke_on_load=True,
        )

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
        resource_id = message['payload']['listener']['id']
        resource_name = message['payload']['listener']['name']
        user_id = None
        project_id = message['payload']['listener']['tenant_id']

        order = Order(resource_id=resource_id,
                      resource_name=resource_name,
                      type=const.RESOURCE_LISTENER,
                      status=state if state else const.STATE_RUNNING,
                      user_id=user_id,
                      project_id=project_id)
        return order


class ListenerCreateEnd(ListenerNotificationBase):
    """Handle the event that listener be created
    """
    event_types = ['listener.create.end']

    def process_notification(self, message, state=None):
        LOG.warn('Do action for event: %s, resource_id: %s',
                 message['event_type'],
                 message['payload']['listener']['id'])

        # Generate uuid of an order
        order_id = uuidutils.generate_uuid()

        unit_price = 0
        unit = 'hour'

        if not state:
            if message['payload']['listener']['admin_state_up']:
                state = const.STATE_RUNNING
            else:
                state = const.STATE_STOPPED

        # Create subscriptions for this order
        for ext in self.product_items.extensions:
            if ext.name.startswith('suspend'):
                sub = ext.obj.create_subscription(message, order_id,
                                                  type=const.STATE_SUSPEND)
                if sub and state==const.STATE_SUSPEND:
                    p = gringutils._quantize_decimal(sub['unit_price'])
                    unit_price += p * sub['quantity']
            elif ext.name.startswith('running'):
                sub = ext.obj.create_subscription(message, order_id,
                                                  type=const.STATE_RUNNING)
                if sub and (not state or state==const.STATE_RUNNING):
                    p = gringutils._quantize_decimal(sub['unit_price'])
                    unit_price += p * sub['quantity']

        # Create an order for this instance
        self.create_order(order_id, unit_price, unit, message, state=state)

        # Notify master, just give master messages it needs
        remarks = 'Listener Has Been Created.'
        action_time = message['timestamp']
        if state:
            self.resource_created_again(order_id, action_time, remarks)
        else:
            self.resource_created(order_id, action_time, remarks)

    def get_unit_price(self, order_id, message, status, cron_time=None):
        unit_price = 0

        if status == const.STATE_STOPPED:
            return unit_price

        # Create subscriptions for this order
        for ext in self.product_items.extensions:
            if ext.name.startswith(status):
                unit_price += ext.obj.get_unit_price(order_id, message)

        return unit_price

    def change_unit_price(self, message, status, order_id):
        quantity = int(message['payload']['listener']['connection_limit']) / 1000
        self.change_order_unit_price(order_id, quantity, status)


services.register_class(ks_client,
                        'network',
                        const.RESOURCE_LISTENER,
                        ListenerCreateEnd)


class ListenerUpdateEnd(ListenerNotificationBase):
    """Handle the events that listener's connection_limit or admin_state_up
    be changed
    """
    event_types = ['listener.update.end']

    def process_notification(self, message):
        LOG.warn('Do action for event: %s, resource_id: %s',
                 message['event_type'],
                 message['payload']['listener']['id'])

        quantity = int(message['payload']['listener']['connection_limit']) / 1000
        admin_state_up = message['payload']['listener']['admin_state_up']

        # Get the order of this resource
        resource_id = message['payload']['listener']['id']
        order = self.get_order_by_resource_id(resource_id)

        if order.get('unit') in ['month', 'year']:
            return

        # Get subscriptions of this order
        subs = self.get_subscriptions(order_id=order['order_id'], type=const.STATE_RUNNING)
        if not subs:
            LOG.warn("The order %s has no subscriptions" % order['order_id'])
            return

        # Notify master
        action_time = message['timestamp']

        ## Listener be resized
        if subs[0]['quantity'] != quantity:
            remarks = 'Listener Has Been Resized'
            self.resource_resized(order['order_id'], action_time, quantity, remarks)

        status = const.STATE_RUNNING if admin_state_up else const.STATE_STOPPED
        if status == order['status']:
            return

        ## Listener be stopped
        if status == const.STATE_STOPPED:
            remarks = 'Listener Has Been Stopped.'
            self.resource_stopped(order['order_id'], action_time, remarks)
        elif status == const.STATE_RUNNING:
        ## Listener be started
            remarks = 'Listener Has Been Started.'
            self.resource_started(order['order_id'], action_time, remarks)


class ListenerDeleteEnd(ListenerNotificationBase):
    """Handle the event that listener be deleted
    """
    event_types = ['listener.delete.end']

    def process_notification(self, message):
        LOG.warn('Do action for event: %s, resource_id: %s',
                 message['event_type'],
                 message['payload']['listener']['id'])

        # Get the order of this resource
        resource_id = message['payload']['listener']['id']
        order = self.get_order_by_resource_id(resource_id)

        if order.get('unit') in ['month', 'year']:
            return

        # Notify master
        action_time = message['timestamp']
        remarks = 'Listener Has Been Deleted'
        self.resource_deleted(order['order_id'], action_time, remarks)


class LoadBalancerDeleteEnd(ListenerNotificationBase):
    """Deleting a loadbalancer will stop all listeners in this loadbalancer
    """
    event_types = ['loadbalancer.delete.end']

    def process_notification(self, message):
        LOG.warn('Do action for event: %s, resource_id: %s',
                 message['event_type'],
                 message['payload']['loadbalancer_id'])

        listener_ids = message['payload']['loadbalancer'].get('listener_ids') or []

        for listener_id in listener_ids:
            try:
                # Get the order of this resource
                order = self.get_order_by_resource_id(listener_id)

                if order.get('unit') in ['month', 'year']:
                    return

                # Notify master
                action_time = message['timestamp']
                remarks = 'Listener Has Been Deleted'
                self.resource_deleted(order['order_id'], action_time, remarks)
            except Exception:
                LOG.exception("Fail to process notification for listener: %s" % listener_id)
