#!/usr/bin/python
"""Plugins for executing specific actions acrronding to notification events.
"""
from oslo.config import cfg
from stevedore import extension

from gringotts import constants as const
from gringotts import utils as gringutils
from gringotts import exception
from gringotts import plugin

from gringotts import services
from gringotts.services import keystone as ks_client

from gringotts.waiter import plugin as waiter_plugin
from gringotts.waiter.plugin import Collection
from gringotts.waiter.plugin import Order

from gringotts.openstack.common import log
from gringotts.openstack.common import uuidutils


LOG = log.getLogger(__name__)

OPTS = [
    cfg.StrOpt('ceilometer_control_exchange',
               default='ceilometer',
               help="Exchange name for Ceilometer notifications"),
]


cfg.CONF.register_opts(OPTS)


class AlarmItem(waiter_plugin.ProductItem):

    def get_collection(self, message):
        """Get collection from message
        """
        product_name = const.PRODUCT_ALARM
        service = const.SERVICE_MONITOR
        region_id = cfg.CONF.region_name
        resource_id = message['payload']['alarm_id']
        resource_name = message['payload']['detail']['name']
        resource_type = const.RESOURCE_ALARM
        resource_volume = 1
        user_id = message['payload']['user_id']
        project_id = message['payload']['project_id']

        return Collection(product_name=product_name,
                          service=service,
                          region_id=region_id,
                          resource_id=resource_id,
                          resource_name=resource_name,
                          resource_type=resource_type,
                          resource_volume=resource_volume,
                          user_id=user_id,
                          project_id=project_id)


class AlarmNotificationBase(waiter_plugin.NotificationBase):

    def __init__(self):
        super(AlarmNotificationBase, self).__init__()
        self.product_items = extension.ExtensionManager(
            namespace='gringotts.alarm.product_item',
            invoke_on_load=True,
        )

    @staticmethod
    def get_exchange_topics(conf):
        """Return a sequence of ExchangeTopics defining the exchange and
        topics to be connected for this plugin.
        """
        return [
            plugin.ExchangeTopics(
                exchange=conf.ceilometer_control_exchange,
                topics=set(topic + ".info"
                           for topic in conf.notification_topics)),
        ]

    def make_order(self, message, state=None):
        """Make an order model for one instance
        """
        resource_id = message['payload']['alarm_id']
        resource_name = message['payload']['detail']['name']
        user_id = message['payload']['user_id']
        project_id = message['payload']['project_id']

        order = Order(resource_id=resource_id,
                      resource_name=resource_name,
                      type=const.RESOURCE_ALARM,
                      status=state if state else const.STATE_RUNNING,
                      user_id=user_id,
                      project_id=project_id)
        return order


class AlarmCreateEnd(AlarmNotificationBase):
    """Handle the event that instance be created, for now, it
    will handle three products: flavor, image and disk
    """
    event_types = ['alarm.creation']

    def process_notification(self, message, state=None):
        LOG.warn('Do action for event: %s, resource_id: %s',
                 message['event_type'],
                 message['payload']['alarm_id'])

        # Generate uuid of an order
        order_id = uuidutils.generate_uuid()

        unit_price = 0
        unit = None

        # Create subscriptions for this order
        for ext in self.product_items.extensions:
            # disk extension is used when instance been stopped and been suspend
            if ext.name.startswith('stopped'):
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

        # Notify master
        remarks = 'Alarm Has Been Created.'
        action_time = message['timestamp']
        if state:
            self.resource_created_again(order_id, action_time, remarks)
        else:
            self.resource_created(order_id, action_time, remarks)


services.register_class(ks_client,
                        'metering',
                        const.RESOURCE_ALARM,
                        AlarmCreateEnd)


class AlarmOnOffEnd(AlarmNotificationBase):
    """Handle the events that instances be stopped, for now,
    it will only handle one product: volume.size.
    """

    #NOTE(suo): 'compute.instance.shutdown2.end' is sent out
    #           by soft shutdown operation
    event_types = ['alarm.on/off']

    def process_notification(self, message):
        LOG.warn('Do action for event: %s, resource_id: %s',
                 message['event_type'],
                 message['payload']['alarm_id'])

        # Get the order of this resource
        resource_id = message['payload']['alarm_id']
        order = self.get_order_by_resource_id(resource_id)

        # Notify master
        action_time = message['timestamp']

        if message['payload']['detail']['action'] == 'off':
            remarks = 'Alarm Has Been Stopped.'
            self.resource_stopped(order['order_id'], action_time, remarks)
        elif message['payload']['detail']['action'] == 'on':
            remarks = 'Alarm Has Been Started.'
            self.resource_started(order['order_id'], action_time, remarks)


class AlarmDeleteEnd(AlarmNotificationBase):
    """Handle the event that instance be deleted
    """
    event_types = ['alarm.deletion']

    def process_notification(self, message):
        LOG.warn('Do action for event: %s, resource_id: %s',
                 message['event_type'],
                 message['payload']['alarm_id'])

        # Get the order of this resource
        resource_id = message['payload']['alarm_id']
        order = self.get_order_by_resource_id(resource_id)

        # Notify master
        action_time = message['timestamp']
        remarks = 'Alarm Has Been Deleted'
        self.resource_deleted(order['order_id'], action_time, remarks)
