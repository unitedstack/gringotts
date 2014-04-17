#!/usr/bin/python
"""Plugins for executing specific actions acrronding to notification events.
"""
from oslo.config import cfg
from stevedore import extension

from gringotts import constants as const
from gringotts import utils as gringutils
from gringotts import exception
from gringotts import plugin
from gringotts.waiter import plugin as waiter_plugin
from gringotts.waiter.plugin import Collection
from gringotts.waiter.plugin import Order

from gringotts.openstack.common import log
from gringotts.openstack.common import uuidutils


LOG = log.getLogger(__name__)

OPTS = [
    cfg.StrOpt('nova_control_exchange',
               default='nova',
               help="Exchange name for Nova notifications"),
]


cfg.CONF.register_opts(OPTS)


class FlavorItem(waiter_plugin.ProductItem):

    def get_collection(self, message):
        """Get collection from message
        """
        instance_type = message['payload']['instance_type']

        product_name = '%s:%s' % (const.PRODUCT_INSTANCE_TYPE_PREFIX,
                                  instance_type)
        service = const.SERVICE_COMPUTE
        region_id = cfg.CONF.region_name
        resource_id = message['payload']['instance_id']
        resource_name = message['payload']['display_name']
        resource_type = const.RESOURCE_INSTANCE
        resource_volume = 1
        user_id = message['payload']['user_id']
        project_id = message['payload']['tenant_id']

        return Collection(product_name=product_name,
                          service=service,
                          region_id=region_id,
                          resource_id=resource_id,
                          resource_name=resource_name,
                          resource_type=resource_type,
                          resource_volume=resource_volume,
                          user_id=user_id,
                          project_id=project_id)


class LicenseItem(waiter_plugin.ProductItem):

    def get_collection(self, message):
        """Get collection from message
        """
        image_name = message['payload']['image_name']
        image_id = message['payload']['image_meta']['base_image_ref']

        product_name = '%s:%s' % (image_name, image_id)
        service = const.SERVICE_COMPUTE
        region_id = cfg.CONF.region_name
        resource_id = message['payload']['instance_id']
        resource_name = message['payload']['display_name']
        resource_type = const.RESOURCE_INSTANCE
        resource_volume = 1
        user_id = message['payload']['user_id']
        project_id = message['payload']['tenant_id']

        return Collection(product_name=product_name,
                          service=service,
                          region_id=region_id,
                          resource_id=resource_id,
                          resource_name=resource_name,
                          resource_type=resource_type,
                          resource_volume=resource_volume,
                          user_id=user_id,
                          project_id=project_id)


class DiskItem(waiter_plugin.ProductItem):

    def get_collection(self, message):
        """Get collection from message
        """
        product_name = const.PRODUCT_VOLUME_SIZE
        service = const.SERVICE_BLOCKSTORAGE
        region_id = cfg.CONF.region_name
        resource_id = message['payload']['instance_id']
        resource_name = message['payload']['display_name']
        resource_type = const.RESOURCE_INSTANCE
        resource_volume = message['payload']['disk_gb']
        user_id = message['payload']['user_id']
        project_id = message['payload']['tenant_id']

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
    namespace='gringotts.instance.product_item',
    invoke_on_load=True,
)


class ComputeNotificationBase(waiter_plugin.NotificationBase):

    @staticmethod
    def get_exchange_topics(conf):
        """Return a sequence of ExchangeTopics defining the exchange and
        topics to be connected for this plugin.
        """
        return [
            plugin.ExchangeTopics(
                exchange=conf.nova_control_exchange,
                topics=set(topic + ".info"
                           for topic in conf.notification_topics)),
        ]

    def make_order(self, message):
        """Make an order model for one instance
        """
        resource_id = message['payload']['instance_id']
        resource_name = message['payload']['display_name']
        user_id = message['payload']['user_id']
        project_id = message['payload']['tenant_id']

        order = Order(resource_id=resource_id,
                      resource_name=resource_name,
                      type=const.RESOURCE_INSTANCE,
                      status=const.STATE_RUNNING,
                      user_id=user_id,
                      project_id=project_id)
        return order


class InstanceCreateEnd(ComputeNotificationBase):
    """Handle the event that instance be created, for now, it
    will handle three products: flavor, image and disk
    """
    event_types = ['compute.instance.create.end']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s, resource_id: %s',
                  message['event_type'],
                  message['payload']['instance_id'])

        # We only care the instance created successfully
        if message['payload']['state'] != 'active':
            instance_id = message['payload']['instance_id']
            LOG.warning('The state of instance %s is not active' % instance_id)
            raise exception.InstanceStateError(instance_id=instance_id,
                                               state=message['payload']['state'])

        # Generate uuid of an order
        order_id = uuidutils.generate_uuid()

        unit_price = 0
        unit = None

        # Create subscriptions for this order
        for ext in product_items.extensions:
            # disk extension is used when instance been stopped and been suspend
            if ext.name.startswith('stopped'):
                ext.obj.create_subscription(message, order_id,
                                            type=const.STATE_STOPPED)
            elif ext.name.startswith('suspend'):
                ext.obj.create_subscription(message, order_id,
                                            type=const.STATE_SUSPEND)
            elif ext.name.startswith('running'):
                sub = ext.obj.create_subscription(message, order_id,
                                                  type=const.STATE_RUNNING)
                if sub:
                    p = gringutils._quantize_decimal(sub['unit_price'])
                    unit_price += p * sub['quantity']
                    unit = sub['unit']

        # Create an order for this instance
        self.create_order(order_id, unit_price, unit, message)

        # Notify master
        remarks = 'Instance Has Been Created.'
        action_time = message['timestamp']
        self.resource_created(order_id, action_time, remarks)


class InstanceStopEnd(ComputeNotificationBase):
    """Handle the events that instances be stopped, for now,
    it will only handle one product: volume.size.
    """
    event_types = ['compute.instance.power_off.end']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s, resource_id: %s',
                  message['event_type'],
                  message['payload']['instance_id'])

        # We only care the instance stopped successfully
        if message['payload']['state'] != 'stopped':
            instance_id = message['payload']['instance_id']
            LOG.warning('The state of instance %s is not stopped' % instance_id)
            raise exception.InstanceStateError(instance_id=instance_id,
                                               state=message['payload']['state'])

        # Get the order of this resource
        resource_id = message['payload']['instance_id']
        order = self.get_order_by_resource_id(resource_id)

        # Notify master
        action_time = message['timestamp']
        change_to = const.STATE_STOPPED
        remarks = 'Instance Has Been Stopped.'
        self.resource_changed(order['order_id'], action_time, change_to, remarks)


class InstanceStartEnd(ComputeNotificationBase):
    """Handle the events that instances be started, for now, it will
    handle two product: flavor and image
    """
    event_types = ['compute.instance.power_on.end']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s, resource_id: %s',
                  message['event_type'],
                  message['payload']['instance_id'])

        # We only care the instance started successfully
        if message['payload']['state'] != 'active':
            instance_id = message['payload']['instance_id']
            LOG.warning('The state of instance %s is not stopped' % instance_id)
            raise exception.InstanceStateError(instance_id=instance_id,
                                               state=message['payload']['state'])

        # Get the order of this resource
        resource_id = message['payload']['instance_id']
        order = self.get_order_by_resource_id(resource_id)

        # Notify master
        action_time = message['timestamp']
        change_to = const.STATE_RUNNING
        remarks = 'Instance Has Been Started.'
        self.resource_changed(order['order_id'], action_time, change_to, remarks)


class InstanceResizeEnd(ComputeNotificationBase):
    """Handle the events that instances be changed
    """
    event_types = ['compute.instance.resize.end']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s, resource_id: %s',
                  message['event_type'],
                  message['payload']['instance_id'])


class InstanceDeleteEnd(ComputeNotificationBase):
    """Handle the event that instance be deleted
    """
    event_types = ['compute.instance.delete.end']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s, resource_id: %s',
                  message['event_type'],
                  message['payload']['instance_id'])

        # We only care the instance deleted successfully
        if message['payload']['state'] != 'deleted':
            instance_id = message['payload']['instance_id']
            LOG.warning('The state of instance %s is not stopped' % instance_id)
            raise exception.InstanceStateError(instance_id=instance_id,
                                               state=message['payload']['state'])

        # Get the order of this resource
        resource_id = message['payload']['instance_id']
        order = self.get_order_by_resource_id(resource_id)

        # Notify master
        action_time = message['timestamp']
        self.resource_deleted(order['order_id'], action_time)


class InstanceSuspendEnd(ComputeNotificationBase):
    """Handle the events that instances be suspend, for now,
    it will only handle one product: volume.size
    """
    event_types = ['compute.instance.suspend']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s, resource_id: %s',
                  message['event_type'],
                  message['payload']['instance_id'])

        # Get the order of this resource
        resource_id = message['payload']['instance_id']
        order = self.get_order_by_resource_id(resource_id)

        # Notify master
        action_time = message['timestamp']
        change_to = const.STATE_SUSPEND
        remarks = 'Instance Has Been Suppend.'
        self.resource_changed(order['order_id'], action_time, change_to, remarks)


class InstanceResumeEnd(ComputeNotificationBase):
    """Handle the events that instances be resumed
    """
    event_types = ['compute.instance.resume']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s, resource_id: %s',
                  message['event_type'],
                  message['payload']['instance_id'])

        # Get the order of this resource
        resource_id = message['payload']['instance_id']
        order = self.get_order_by_resource_id(resource_id)

        # Notify master, just give master messages it needs
        action_time = message['timestamp']
        change_to = const.STATE_RUNNING
        remarks = 'Instance Has Been Resumed.'
        self.resource_changed(order['order_id'], action_time, change_to, remarks)
