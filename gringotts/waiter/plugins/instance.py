#!/usr/bin/python
"""Plugins for executing specific actions acrronding to notification events.
"""
from oslo.config import cfg
from stevedore import extension

from gringotts import context
from gringotts import db
from gringotts.db import models as db_models
from gringotts import exception
from gringotts import master
from gringotts import plugin
from gringotts.waiter import plugin as waiter_plugin
from gringotts.waiter.plugin import Collection

from gringotts.openstack.common import log
from gringotts.openstack.common import uuidutils


LOG = log.getLogger(__name__)

OPTS = [
    cfg.StrOpt('nova_control_exchange',
               default='nova',
               help="Exchange name for Nova notifications"),
]


cfg.CONF.register_opts(OPTS)

db_conn = db.get_connection(cfg.CONF)
master_api = master.API()


class FlavorItem(waiter_plugin.ProductItem):

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

        return Collection(product_name=product_name,
                          service=service,
                          region_id=region_id,
                          resource_id=resource_id,
                          resource_name=resource_name,
                          resource_type=resource_type,
                          resource_status=resource_status,
                          resource_volume=resource_volume,
                          user_id=user_id,
                          project_id=project_id)


class ImageItem(waiter_plugin.ProductItem):

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

        return Collection(product_name=product_name,
                          service=service,
                          region_id=region_id,
                          resource_id=resource_id,
                          resource_name=resource_name,
                          resource_type=resource_type,
                          resource_status=resource_status,
                          resource_volume=resource_volume,
                          user_id=user_id,
                          project_id=project_id)


class DiskItem(waiter_plugin.ProductItem):

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

        return Collection(product_name=product_name,
                          service=service,
                          region_id=region_id,
                          resource_id=resource_id,
                          resource_name=resource_name,
                          resource_type=resource_type,
                          resource_status=resource_status,
                          resource_volume=resource_volume,
                          user_id=user_id,
                          project_id=project_id)


product_items = extension.ExtensionManager(
    namespace='gringotts.instance.product_item',
    invoke_on_load=True,
)


class ComputeNotificationBase(plugin.NotificationBase):
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

    def create_order(self, order_id, unit_price, unit, message):
        """Create an order for one instance
        """
        resource_id = message['payload']['instance_id']
        resource_name = message['payload']['hostname']
        resource_status = message['payload']['state']
        user_id = message['payload']['user_id']
        project_id = message['payload']['tenant_id']

        order_in = db_models.Order(order_id=order_id,
                                   resource_id=resource_id,
                                   resource_name=resource_name,
                                   resource_status=resource_status,
                                   type='instance',
                                   unit_price=unit_price,
                                   unit=unit,
                                   amount=0,
                                   cron_time=None,
                                   status=None,
                                   user_id=user_id,
                                   project_id=project_id)

        try:
            order = db_conn.create_order(context.get_admin_context(), order_in)
        except Exception:
            LOG.exception('Fail to create order: %s' %
                          order_in.as_dict())
            raise exception.DBError(reason='Fail to create order')
        return order


class InstanceCreateEnd(ComputeNotificationBase):
    """Handle the event that instance be created, for now, it
       will handle three products: flavor, image and disk
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

        # Generate uuid of an order
        order_id = uuidutils.generate_uuid()

        unit_price = 0
        unit = None

        # Create subscriptions for this order
        for ext in product_items.extensions:
            # disk extension is used when instance been stopped
            if ext.name == 'disk':
                ext.obj.create_subscription(message, order_id,
                                            type='stopped', status='inactive')
            else:
                sub = ext.obj.create_subscription(message, order_id,
                                                  type='started', status='active')
                if sub:
                    unit_price += sub.unit_price * sub.resource_volume
                    unit = sub.unit

        # Create an order for this instance
        order = self.create_order(order_id, unit_price, unit, message)

        remarks = 'Instance Has Been Created.'
        action_time = message['timestamp']

        # Notify master, just give master messages it needs
        master_api.resource_created(context.get_admin_context(),
                                    order.order_id,
                                    action_time, remarks)


class InstanceStopEnd(ComputeNotificationBase):
    """Handle the events that instances be stopped, for now,
       it will only handle one product: volume.size.
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

        # Get the order of this resource
        resource_id = message['payload']['instance_id']
        order = db_conn.get_order_by_resource_id(context.get_admin_context(),
                                                 resource_id)

        action_time = message['timestamp']
        change_to = 'stopped'
        remarks = 'Instance Has Been Stopped.'

        # Notify master, just give master messages it needs
        master_api.resource_changed(context.get_admin_context(),
                                    order.order_id,
                                    action_time, change_to, remarks)


class InstanceStartEnd(ComputeNotificationBase):
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

        # Get the order of this resource
        resource_id = message['payload']['instance_id']
        order = db_conn.get_order_by_resource_id(context.get_admin_context(),
                                                 resource_id)

        action_time = message['timestamp']
        change_to = 'started'
        remarks = 'Instance Has Been Started.'

        # Notify master, just give master messages it needs
        master_api.resource_changed(context.get_admin_context(),
                                    order.order_id,
                                    action_time, change_to, remarks)


class InstanceResizeEnd(ComputeNotificationBase):
    """Handle the events that instances be changed
    """
    event_types = ['compute.instance.resize.end']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s', message['event_type'])

        # Get the order of this instance

        # Create a new subscription for this new flavor,
        # its initial status=='inactive', and type=='resized'

        # Notify master


class InstanceDeleteEnd(ComputeNotificationBase):
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

        # Get the order of this resource
        resource_id = message['payload']['instance_id']
        order = db_conn.get_order_by_resource_id(context.get_admin_context(),
                                                 resource_id)
        action_time = message['timestamp']

        # Notify master, just give master messages it needs
        master_api.resource_deleted(context.get_admin_context(),
                                    order.order_id, action_time)
