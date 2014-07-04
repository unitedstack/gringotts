from gringotts.checker import notifier
from gringotts.openstack.common import log


LOG = log.getLogger(__name__)


class SMSNotifier(notifier.Notifier):

    @staticmethod
    def notify_has_owed(context, account, contact, orders):
        pass

    @staticmethod
    def notify_before_owed(context, account, contact, price_per_day, days_to_owe):
        pass

    @staticmethod
    def notify_account_charged(context, account, contact, value, bonus=None):
        pass
