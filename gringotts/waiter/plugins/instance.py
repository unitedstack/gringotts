#!/usr/bin/python
"""Plugins for executing specific actions acrronding to notification events.
"""
import datetime

from oslo.config import cfg
from stevedore import extension

from gringotts import db
from gringotts.waiter import plugin
from gringotts.waiter.plugin import Collection
from gringotts import exception
from gringotts.db import models as db_models
from gringotts import master

from gringotts.openstack.common import log
from gringotts.openstack.common import uuidutils
from gringotts.openstack.common import context


LOG = log.getLogger(__name__)


OPTS = [
    cfg.StrOpt('nova_control_exchange',
               default='nova',
               help="Exchange name for Nova notifications"),
]


cfg.CONF.register_opts(OPTS)

db_conn = db.get_connection(cfg.CONF)
master_api = master.API()


class FlavorItem(plugin.ProductItem):

    @staticmethod
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
        user_id = message['payload']['user_id']
        project_id = message['payload']['tenant_id']
        action_time = message['timestamp']

        return Collection(product_name=product_name,
                          service=service,
                          region_id=region_id,
                          resource_id=resource_id,
                          resource_name=resource_name,
                          resource_type=resource_type,
                          resource_status=resource_status,
                          user_id=user_id,
                          project_id=project_id,
                          action_time=action_time)


class ImageItem(plugin.ProductItem):

    @staticmethod
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
        user_id = message['payload']['user_id']
        project_id = message['payload']['tenant_id']
        action_time = message['timestamp']

        return Collection(product_name=product_name,
                          service=service,
                          region_id=region_id,
                          resource_id=resource_id,
                          resource_name=resource_name,
                          resource_type=resource_type,
                          resource_status=resource_status,
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
            raise exception.InstanceStateError(instance_id=instance_id)

        subs_products = []

        # Create subscriptions
        for item in product_items.extensions:
            sub, product = item.obj.create_subscription(message)
            subs_prods.append((sub, product))

        remarks = 'Instance Has Been Created.'
        action_time = message['timestamp']

        # Notify master, just give master messages it needs
        master_api.resource_created(context.RequestContext(),
                                    subs_products, action_time, remarks)


class InstanceStartEnd(plugin.ComputeNotificationBase):
    """Handle the events that instances be started, for now, it will
    handle two product: flavor and image
    """
    event_types = ['compute.instance.start.end']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s', message['event_type'])


class InstanceStopEnd(plugin.ComputeNotificationBase):
    """Handle the events that instances be stopped, for now,
       it will only handle one product: stop
    """
    event_types = ['compute.instance.stop.end']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s', message['event_type'])


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
