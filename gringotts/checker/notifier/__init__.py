import abc

from stevedore import extension
from gringotts.openstack.common import log


LOG = log.getLogger(__name__)


class NotifierService(object):

    EXTENSIONS_NAMESPACE = 'gringotts.notifier'

    def __init__(self, level):
        self.level = level or 0
        self.notifiers = []
        extensions = extension.ExtensionManager(self.EXTENSIONS_NAMESPACE,
                                                invoke_on_load=True)
        if self.level == 0:
            self.notifiers.append(extensions['log'].obj)
        elif self.level == 1:
            self.notifiers.append(extensions['log'].obj)
            self.notifiers.append(extensions['email'].obj)
        else:
            self.notifiers.append(extensions['log'].obj)
            self.notifiers.append(extensions['email'].obj)
            self.notifiers.append(extensions['sms'].obj)

    def notify_before_owed(self, context, account, contact, price_per_day, days_to_owe):
        for notifier in self.notifiers:
            notifier.notify_before_owed(context, account, contact, price_per_day, days_to_owe)

    def notify_has_owed(self, context, account, contact, orders):
        for notifier in self.notifiers:
            notifier.notify_has_owed(context, account, contact, orders)


class Notifier(object):
    """Base class for notifier"""

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def notify_has_owed(context, account, contact, orders):
        """Notify account has owed
        """

    @abc.abstractmethod
    def notify_before_owed(context, account, contact, price_per_day, days_to_owe):
        """Notify account who will owe in days_to_owe
        """
