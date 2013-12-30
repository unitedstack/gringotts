#!/usr/bin/python
"""Plugins for executing specific actions acrronding to notification events.
"""
from gringotts import plugin
from oslo.config import cfg

from gringotts.openstack.common import log


LOG = log.getLogger(__name__)


OPTS = [
    cfg.StrOpt('cinder_control_exchange',
               default='cinder',
               help="Exchange name for Cinder notifications"),
]


cfg.CONF.register_opts(OPTS)


class VolumeNotificationBase(plugin.NotificationBase):
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


class VolumeCreateEnd(VolumeNotificationBase):
    """Handle the event that volume be created
    """
    event_types = ['volume.create.end']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s', message['event_type'])


class VolumeChangeEnd(VolumeNotificationBase):
    """Handle the events that volume be changed
    """
    event_types = ['volume.resize.end']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s', message['event_type'])


class VolumeDeleteEnd(VolumeNotificationBase):
    """Handle the event that volume be deleted
    """
    event_types = ['volume.delete.end']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s', message['event_type'])
