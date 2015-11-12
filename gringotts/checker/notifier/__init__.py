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

    def notify_before_owed(self, context, account, contact, projects, price_per_day, days_to_owe, **kwargs):
        for notifier in self.notifiers:
            notifier.notify_before_owed(context, account, contact, projects, price_per_day, days_to_owe, **kwargs)

    def notify_has_owed(self, context, account, contact, projects, **kwargs):
        for notifier in self.notifiers:
            notifier.notify_has_owed(context, account, contact, projects, **kwargs)

    def notify_order_billing_owed(self, context, account, contact, order, **kwargs):
        for notifier in self.notifiers:
            notifier.notify_order_billing_owed(context, account, contact, order, **kwargs)

    def notify_account_charged(self, context, account, contact, type, value, bonus=None, **kwargs):
        for notifier in self.notifiers:
            notifier.notify_account_charged(context, account, contact, type, value, bonus=bonus, **kwargs)

    def send_account_info(self, context, account_infos, email_addr_name):
        for notifier in self.notifiers:
            notifier.send_account_info(context, account_infos, email_addr_name)


class Notifier(object):
    """Base class for notifier"""

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def notify_has_owed(context, account, contact, projects, **kwargs):
        """Notify account has owed
        """

    @abc.abstractmethod
    def notify_before_owed(context, account, contact, projects,
                           price_per_day, days_to_owe, **kwargs):
        """Notify account who will owe in days_to_owe
        """

    @abc.abstractmethod
    def notify_account_charged(context, account, contact, type, value, bonus=None, **kwargs):
        """Notify account has charged successfully
        """

    @abc.abstractmethod
    def notify_order_billing_owed(context, account, contact, order,**kwargs):
        """Notify order billing owed
        """
