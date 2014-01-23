#!/usr/bin/python
"""Plugins for executing specific actions acrronding to notification events.
"""
from oslo.config import cfg
from stevedore import extension

from gringotts import constants as const
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
    cfg.StrOpt('cinder_control_exchange',
               default='openstack',
               help="Exchange name for Cinder notifications"),
]


cfg.CONF.register_opts(OPTS)

db_conn = db.get_connection(cfg.CONF)
master_api = master.API()


class SizeItem(waiter_plugin.ProductItem):

    def get_collection(self, message):
        """Get collection from message
        """
        product_name = const.PRODUCT_SNAPSHOT_SIZE
        service = const.SERVICE_BLOCKSTORAGE
        region_id = 'default'
        resource_id = message['payload']['snapshot_id']
        resource_name = message['payload']['display_name']
        resource_type = const.RESOURCE_SNAPSHOT
        resource_volume = message['payload']['volume_size']
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
    namespace='gringotts.snapshot.product_item',
    invoke_on_load=True,
)


class SnapshotNotificationBase(plugin.NotificationBase):
    @staticmethod
    def get_exchange_topics(conf):
        """Return a sequence of ExchangeTopics defining the exchange and
        topics to be connected for this plugin.
        """
        return [
            plugin.ExchangeTopics(
                exchange=conf.cinder_control_exchange,
                topics=set(topic + ".info"
                           for topic in conf.notification_topics)),
        ]

    def create_order(self, order_id, unit_price, unit, message):
        """Create an order for one instance
        """
        resource_id = message['payload']['snapshot_id']
        resource_name = message['payload']['display_name']
        user_id = message['payload']['user_id']
        project_id = message['payload']['tenant_id']

        order_in = db_models.Order(order_id=order_id,
                                   resource_id=resource_id,
                                   resource_name=resource_name,
                                   type=const.RESOURCE_SNAPSHOT,
                                   unit_price=unit_price,
                                   unit=unit,
                                   total_price=0,
                                   cron_time=None,
                                   date_time=None,
                                   status=const.STATE_RUNNING,
                                   user_id=user_id,
                                   project_id=project_id)

        try:
            order = db_conn.create_order(context.get_admin_context(), order_in)
        except Exception:
            LOG.exception('Fail to create order: %s' %
                          order_in.as_dict())
            raise exception.DBError(reason='Fail to create order')
        return order


class SnapshotCreateEnd(SnapshotNotificationBase):
    """Handle the event that snapshot be created
    """
    event_types = ['snapshot.create.end']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s', message['event_type'])

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
                    unit_price += sub.unit_price * sub.quantity
                    unit = sub.unit

        # Create an order for this instance
        order = self.create_order(order_id, unit_price, unit, message)

        remarks = 'Snapshot Has Been Created.'
        action_time = message['timestamp']

        # Notify master, just give master messages it needs
        master_api.resource_created(context.get_admin_context(),
                                    order.order_id,
                                    action_time, remarks)


class SnapshotDeleteEnd(SnapshotNotificationBase):
    """Handle the event that snapthot be deleted
    """
    event_types = ['snapshot.delete.end']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s', message['event_type'])

        # Get the order of this resource
        resource_id = message['payload']['snapshot_id']
        order = db_conn.get_order_by_resource_id(context.get_admin_context(),
                                                 resource_id)
        action_time = message['timestamp']

        master_api.resource_deleted(context.get_admin_context(),
                                    order.order_id, action_time)
