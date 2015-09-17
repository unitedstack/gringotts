#!/usr/bin/python
"""Plugins for executing specific actions acrronding to notification events.
"""
import datetime

from oslo.config import cfg
from stevedore import extension

from gringotts import constants as const
from gringotts import utils as gringutils
from gringotts import exception
from gringotts import plugin
from gringotts.waiter import plugin as waiter_plugin
from gringotts.waiter.plugin import Collection
from gringotts.waiter.plugin import Order

from gringotts import services
from gringotts.services import keystone as ks_client

from gringotts.openstack.common import log
from gringotts.openstack.common import uuidutils
from gringotts.openstack.common import timeutils


LOG = log.getLogger(__name__)


ISO8601_UTC_TIME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'


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
        image_label = message['payload']['image_meta'].get('image_label') or 'default'

        product_name = 'license:%s' % image_label
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


class ComputeNotificationBase(waiter_plugin.NotificationBase):

    def __init__(self):
        super(ComputeNotificationBase, self).__init__()
        self.product_items = extension.ExtensionManager(
            namespace='gringotts.instance.product_item',
            invoke_on_load=True,
        )

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

    def make_order(self, message, state=None):
        """Make an order model for one instance
        """
        resource_id = message['payload']['instance_id']
        resource_name = message['payload']['display_name']
        user_id = message['payload']['user_id']
        project_id = message['payload']['tenant_id']

        order = Order(resource_id=resource_id,
                      resource_name=resource_name,
                      type=const.RESOURCE_INSTANCE,
                      status=state if state else const.STATE_RUNNING,
                      user_id=user_id,
                      project_id=project_id)
        return order


class InstanceCreateEnd(ComputeNotificationBase):
    """Handle the event that instance be created, for now, it
    will handle three products: flavor, image and disk
    """
    event_types = ['compute.instance.create.end']

    def process_notification(self, message, state=None):
        LOG.warn('Do action for event: %s, resource_id: %s',
                 message['event_type'],
                 message['payload']['instance_id'])

        # Generate uuid of an order
        order_id = uuidutils.generate_uuid()

        unit_price = 0
        unit = None

        # Create subscriptions for this order
        for ext in self.product_items.extensions:
            # disk extension is used when instance been stopped and been suspend
            if ext.name.startswith('stopped'):
                sub = ext.obj.create_subscription(message, order_id,
                                                  type=const.STATE_STOPPED)
                if sub and state==const.STATE_STOPPED:
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
        remarks = 'Instance Has Been Created.'
        action_time = message['timestamp']
        if state:
            self.resource_created_again(order_id, action_time, remarks)
        else:
            self.resource_created(order_id, action_time, remarks)

    def get_unit_price(self, message, status, cron_time=None):
        unit_price = 0

        if isinstance(cron_time, basestring):
            cron_time = timeutils.parse_strtime(cron_time,
                                                fmt=ISO8601_UTC_TIME_FORMAT)

        #delta = cron_time - timeutils.utcnow()
        #if status == const.STATE_STOPPED and delta > datetime.timedelta(hours=1):
        #    return 0

        # didn't check the stopped instance for now
        if status == const.STATE_STOPPED:
            return

        for ext in self.product_items.extensions:
            if ext.name.startswith(status):
                unit_price += ext.obj.get_unit_price(message)

        return unit_price

    def change_unit_price(self, message, status, order_id):
        """Just change the unit price that may changes, so we only consider the flavor"""
        instance_type = message['payload']['instance_type']

        product_name = '%s:%s' % (const.PRODUCT_INSTANCE_TYPE_PREFIX,
                                  instance_type)
        service = const.SERVICE_COMPUTE
        region_id = cfg.CONF.region_name

        self.change_flavor_unit_price(order_id, product_name, service, region_id, status)


services.register_class(ks_client,
                        'compute',
                        const.RESOURCE_INSTANCE,
                        InstanceCreateEnd)


class InstanceStopEnd(ComputeNotificationBase):
    """Handle the events that instances be stopped, for now,
    it will only handle one product: volume.size.
    """

    #NOTE(suo): 'compute.instance.shutdown2.end' is sent out
    #           by soft shutdown operation
    event_types = ['compute.instance.power_off.end',
                   'compute.instance.shutdown2.end']

    def process_notification(self, message):
        LOG.warn('Do action for event: %s, resource_id: %s',
                 message['event_type'],
                 message['payload']['instance_id'])

        # Get the order of this resource
        resource_id = message['payload']['instance_id']
        order = self.get_order_by_resource_id(resource_id)

        # Notify master
        action_time = message['timestamp']
        self.instance_stopped(order['order_id'], action_time)


class InstanceStartEnd(ComputeNotificationBase):
    """Handle the events that instances be started, for now, it will
    handle two product: flavor and image
    """
    event_types = ['compute.instance.power_on.end',
                   'compute.instance.reboot.end']

    def process_notification(self, message):
        LOG.warn('Do action for event: %s, resource_id: %s',
                 message['event_type'],
                 message['payload']['instance_id'])

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
    event_types = ['compute.instance.local_resize.end']

    def process_notification(self, message):
        LOG.warn('Do action for event: %s, resource_id: %s',
                 message['event_type'],
                 message['payload']['instance_id'])

        # Get the order of this resource
        resource_id = message['payload']['instance_id']
        order = self.get_order_by_resource_id(resource_id)

        new_flavor = message['payload']['instance_type']
        old_flavor = message['payload']['old_instance_type']

        if new_flavor == old_flavor:
            return

        new_flavor = '%s:%s' % (const.PRODUCT_INSTANCE_TYPE_PREFIX,
                                new_flavor)
        old_flavor = '%s:%s' % (const.PRODUCT_INSTANCE_TYPE_PREFIX,
                                old_flavor)
        service = const.SERVICE_COMPUTE
        region_id = cfg.CONF.region_name

        action_time = message['timestamp']
        remarks = 'Instance Has Been Resized'
        self.instance_resized(order['order_id'], action_time,
                              new_flavor, old_flavor,
                              service, region_id, remarks)


class InstanceDeleteEnd(ComputeNotificationBase):
    """Handle the event that instance be deleted
    """
    event_types = ['compute.instance.delete.end']

    def process_notification(self, message):
        LOG.warn('Do action for event: %s, resource_id: %s',
                 message['event_type'],
                 message['payload']['instance_id'])

        # Get the order of this resource
        resource_id = message['payload']['instance_id']
        order = self.get_order_by_resource_id(resource_id)

        # Notify master
        action_time = message['timestamp']
        remarks = 'Instance Has Been Deleted'
        self.resource_deleted(order['order_id'], action_time, remarks)


class InstanceSuspendEnd(ComputeNotificationBase):
    """Handle the events that instances be suspend, for now,
    it will only handle one product: volume.size
    """
    event_types = ['compute.instance.suspend']

    def process_notification(self, message):
        LOG.warn('Do action for event: %s, resource_id: %s',
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
        LOG.warn('Do action for event: %s, resource_id: %s',
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
