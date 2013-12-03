"""Base class for plugins.
"""

import abc
import collections
import fnmatch
from oslo.config import cfg
import six

# Import this option so every Notification plugin can use it freely.
cfg.CONF.import_opt('notification_topics',
                    'gringotts.openstack.common.notifier.rpc_notifier')


ExchangeTopics = collections.namedtuple('ExchangeTopics',
                                        ['exchange', 'topics'])


class PluginBase(object):
    """Base class for all plugins.
    """


@six.add_metaclass(abc.ABCMeta)
class NotificationBase(PluginBase):
    """Base class for plugins that support the notification API."""

    @abc.abstractproperty
    def event_types(self):
        """Return a sequence of strings defining the event types to be
        given to this plugin.
        """

    @abc.abstractmethod
    def get_exchange_topics(self, conf):
        """Return a sequence of ExchangeTopics defining the exchange and
        topics to be connected for this plugin.

        :param conf: Configuration.
        """

    @abc.abstractmethod
    def process_notification(self, message):
        """Return a sequence of Counter instances for the given message.

        :param message: Message to process.
        """

    @staticmethod
    def _handle_event_type(event_type, event_type_to_handle):
        """Check whether event_type should be handled according to
        event_type_to_handle.

        """
        return any(map(lambda e: fnmatch.fnmatch(event_type, e),
                       event_type_to_handle))

    def do_actions(self, notification):
        """Do actions based on *process_notification* for the given
        notification, if it's handled by this notification handler.

        :param notification: The notification to process.

        """
        if self._handle_event_type(notification['event_type'],
                                   self.event_types):
            self.process_notification(notification)
