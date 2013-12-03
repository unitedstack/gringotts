#!/usr/bin/python
"""Plugins for executing specific actions acrronding to notification events.
"""

from oslo.config import cfg
from gringotts import plugin

from gringotts.openstack.common import log


LOG = log.getLogger(__name__)


OPTS = [
    cfg.StrOpt('nova_control_exchange',
               default='nova',
               help="Exchange name for Nova notifications"),
]


cfg.CONF.register_opts(OPTS)


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
    """Handle the event that instance be created successfully
    """
    event_types = ['compute.instance.create.end']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s', message['event_type'])


class InstanceChangeEnd(ComputeNotificationBase):
    """Handle the events that instances be changed successfully
    """
    event_types = ['compute.instance.start.end',
                   'compute.instance.stop.end',
                   'compute.instance.resize.end']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s', message['event_type'])


class InstanceDeleteEnd(ComputeNotificationBase):
    """Handle the event that instance be deleted successfully
    """
    event_types = ['compute.instance.delete.end']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s', message['event_type'])
