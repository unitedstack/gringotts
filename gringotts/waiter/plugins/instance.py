#!/usr/bin/python
"""Plugins for executing specific actions acrronding to notification events.
"""
from oslo.config import cfg
from stevedore import extension

from gringotts import db
from gringotts import exception
from gringotts import master
from gringotts.waiter import plugin
from gringotts.waiter.plugin import Collection

from gringotts.openstack.common import context
from gringotts.openstack.common import log
from gringotts.openstack.common import timeutils


LOG = log.getLogger(__name__)

TIMESTAMP_TIME_FORMAT = '%Y-%m-%d %H:%M:%S.%f'


OPTS = [
    cfg.StrOpt('nova_control_exchange',
               default='nova',
               help="Exchange name for Nova notifications"),
]


cfg.CONF.register_opts(OPTS)

db_conn = db.get_connection(cfg.CONF)
master_api = master.API()


class FlavorItem(plugin.ProductItem):

    def get_collection(self, message):
        """Get collection from message
        """
        instance_type = message['payload']['instance_type']

        product_name = 'instance:%s' % instance_type
        service = 'Compute'
        region_id = 'default'
        resource_id = message['payload']['instance_id']
        resource_name = message['payload']['hostname']
        resource_type = 'instance'
        resource_status = message['payload']['state']
        resource_volume = 1
        user_id = message['payload']['user_id']
        project_id = message['payload']['tenant_id']
        action_time = timeutils.parse_isotime(message['timestamp'])

        return Collection(product_name=product_name,
                          service=service,
                          region_id=region_id,
                          resource_id=resource_id,
                          resource_name=resource_name,
                          resource_type=resource_type,
                          resource_status=resource_status,
                          resource_volume=resource_volume,
                          user_id=user_id,
                          project_id=project_id,
                          action_time=action_time)


class ImageItem(plugin.ProductItem):

    def get_collection(self, message):
        """Get collection from message
        """
        image_name = message['payload']['image_name']
        image_id = message['payload']['image_meta']['base_image_ref']

        product_name = '%s-%s' % (image_name, image_id)
        service = 'Compute'
        region_id = 'default'
        resource_id = message['payload']['instance_id']
        resource_name = message['payload']['hostname']
        resource_type = 'instance'
        resource_status = message['payload']['state']
        resource_volume = 1
        user_id = message['payload']['user_id']
        project_id = message['payload']['tenant_id']
        action_time = timeutils.parse_isotime(message['timestamp'])

        return Collection(product_name=product_name,
                          service=service,
                          region_id=region_id,
                          resource_id=resource_id,
                          resource_name=resource_name,
                          resource_type=resource_type,
                          resource_status=resource_status,
                          resource_volume=resource_volume,
                          user_id=user_id,
                          project_id=project_id,
                          action_time=action_time)


class DiskItem(plugin.ProductItem):

    def get_collection(self, message):
        """Get collection from message
        """
        product_name = 'volume.size'
        service = 'BlockStorage'
        region_id = 'default'
        resource_id = message['payload']['instance_id']
        resource_name = message['payload']['hostname']
        resource_type = 'instance'
        resource_status = message['payload']['state']
        resource_volume = message['payload']['disk_gb']
        user_id = message['payload']['user_id']
        project_id = message['payload']['tenant_id']
        action_time = timeutils.parse_isotime(message['timestamp'])

        return Collection(product_name=product_name,
                          service=service,
                          region_id=region_id,
                          resource_id=resource_id,
                          resource_name=resource_name,
                          resource_type=resource_type,
                          resource_status=resource_status,
                          resource_volume=resource_volume,
                          user_id=user_id,
                          project_id=project_id,
                          action_time=action_time)


product_items = extension.ExtensionManager(
    namespace='gringotts.instance.product_item',
    invoke_on_load=True,
)


class InstanceCreateEnd(plugin.ComputeNotificationBase):
    """Handle the event that instance be created, for now, it
       will handle two products: flavor and image
    """
    event_types = ['compute.instance.create.end']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s', message['event_type'])

        # We only care the instance created successfully
        if message['payload']['state'] != 'active':
            instance_id = message['payload']['instance_id']
            LOG.warning('The state of instance %s is not active' % instance_id)
            raise exception.InstanceStateError(instance_id=instance_id,
                                               state=message['payload']['state'])

        subscriptions = []

        # Create subscriptions
        for ext in product_items.extensions:
            # disk extension is used when instance been stopped
            if ext.name == 'disk':
                ext.obj.create_subscription(message, status='inactive')
            else:
                sub = ext.obj.create_subscription(message)
                subscriptions.append(sub)

        remarks = 'Instance Has Been Created.'
        action_time = timeutils.parse_strtime(message['timestamp'],
                                              fmt=TIMESTAMP_TIME_FORMAT)

        # Notify master, just give master messages it needs
        master_api.resource_created(context.RequestContext(),
                                    subscriptions, action_time, remarks)


class InstanceStartEnd(plugin.ComputeNotificationBase):
    """Handle the events that instances be started, for now, it will
    handle two product: flavor and image
    """
    event_types = ['compute.instance.power_on.end']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s', message['event_type'])

        # We only care the instance started successfully
        if message['payload']['state'] != 'active':
            instance_id = message['payload']['instance_id']
            LOG.warning('The state of instance %s is not stopped' % instance_id)
            raise exception.InstanceStateError(instance_id=instance_id,
                                               state=message['payload']['state'])

        resource_id = message['payload']['instance_id']

        # Get all subscriptions, include active and inactive
        subscriptions = self.get_subscriptions(resource_id)

        remarks = 'Instance Has Been Started.'
        action_time = timeutils.parse_strtime(message['timestamp'],
                                              fmt=TIMESTAMP_TIME_FORMAT)

        # Notify master, just give master messages it needs
        master_api.resource_started(context.RequestContext(),
                                    subscriptions,
                                    action_time, remarks)


class InstanceStopEnd(plugin.ComputeNotificationBase):
    """Handle the events that instances be stopped, for now,
       it will only handle one product: volume.size
    """
    event_types = ['compute.instance.power_off.end']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s', message['event_type'])

        # We only care the instance stopped successfully
        if message['payload']['state'] != 'stopped':
            instance_id = message['payload']['instance_id']
            LOG.warning('The state of instance %s is not stopped' % instance_id)
            raise exception.InstanceStateError(instance_id=instance_id,
                                               state=message['payload']['state'])

        # Get all subscriptions
        resource_id = message['payload']['instance_id']
        subscriptions = self.get_subscriptions(resource_id)

        remarks = 'Instance Has Been Stopped.'
        action_time = timeutils.parse_strtime(message['timestamp'],
                                              fmt=TIMESTAMP_TIME_FORMAT)

        # Notify master, just give master messages it needs
        master_api.resource_changed(context.RequestContext(),
                                    subscriptions,
                                    action_time, remarks)


class InstanceResizeEnd(plugin.ComputeNotificationBase):
    """Handle the events that instances be changed
    """
    event_types = ['compute.instance.resize.end']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s', message['event_type'])


class InstanceDeleteEnd(plugin.ComputeNotificationBase):
    """Handle the event that instance be deleted
    """
    event_types = ['compute.instance.delete.end']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s', message['event_type'])

        # We only care the instance stopped successfully
        if message['payload']['state'] != 'deleted':
            instance_id = message['payload']['instance_id']
            LOG.warning('The state of instance %s is not stopped' % instance_id)
            raise exception.InstanceStateError(instance_id=instance_id,
                                               state=message['payload']['state'])

        # Get active subscriptions
        resource_id = message['payload']['instance_id']
        subscriptions = self.get_subscriptions(resource_id,
                                               status='active')

        action_time = timeutils.parse_strtime(message['timestamp'],
                                              fmt=TIMESTAMP_TIME_FORMAT)

        # Notify master, just give master messages it needs
        master_api.resource_deleted(context.RequestContext(),
                                    subscriptions, action_time)
