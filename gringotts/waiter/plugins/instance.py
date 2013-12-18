#!/usr/bin/python
"""Plugins for executing specific actions acrronding to notification events.
"""
import datetime

from oslo.config import cfg

from gringotts import db
from gringotts import plugin
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


def _get_products(message):
    """Get product id from message info
    """
    instance_type = message['payload']['instance_type']
    product_name = 'instance:%s' % instance_type
    service = 'Compute'
    region_id = 'default'

    filters = dict(name=product_name,
                   service=service,
                   region_id=region_id)

    result = list(db_conn.get_products(None, filters=filters))

    if len(result) > 1:
        error = "Duplicated products with name(%s) within service(%s) in region_id(%s)" % \
                (product_name, service, region_id)
        LOG.warning(error)
        raise exception.DuplicatedProduct(reason=error)

    if len(result) == 0:
        error = "Product with name(%s) within service(%s) in region_id(%s) not found" % \
                (product_name, service, region_id)
        LOG.warning(error)
        raise exception.ProductNameNotFound(product_name=product_name)

    return result[0]


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


class InstanceCreateEnd(ComputeNotificationBase):
    """Handle the event that instance be created
    """
    event_types = ['compute.instance.create.end']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s', message['event_type'])

        # We only care the instance created successfully
        if message['payload']['state'] != 'active':
            instance_id = message['payload']['instance_id']
            LOG.warning('The state of instance %s is not active' % instance_id)
            raise exception.InstanceStateError(instance_id=instance_id)

        # Get product from db based on message info
        products = _get_products(message)

        # Create subscription for this resource
        subscription_id = uuidutils.generate_uuid()
        resource_id = message['payload']['instance_id']
        resource_name = message['payload']['hostname']
        resource_type = 'instance'
        resource_status = message['payload']['state']
        product_id = product.product_id
        current_fee = 0
        cron_time = None
        status = 'active'
        user_id = message['payload']['user_id']
        project_id = message['payload']['tenant_id']

        subscription = db_models.Subscription(
                subscription_id, resource_id,
                resource_name, resource_type, resource_status, product_id,
                current_fee, cron_time, status, user_id, project_id)

        try:
            db_conn.create_subscription(None, subscription)
        except Exception:
            LOG.exception('Fail to create subscription: %s' % \
                          subscription.as_dict())
            raise exception.DBError(reason='Fail to create subscription')

        # Notify master, just give master messages it needs
        master_api.instance_created(context.RequestContext(),
                                    message, subscription, product)
        LOG.debug('I am here')


class InstanceChangeEnd(ComputeNotificationBase):
    """Handle the events that instances be changed
    """
    event_types = ['compute.instance.start.end',
                   'compute.instance.stop.end',
                   'compute.instance.resize.end']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s', message['event_type'])


class InstanceDeleteEnd(ComputeNotificationBase):
    """Handle the event that instance be deleted
    """
    event_types = ['compute.instance.delete.end']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s', message['event_type'])
