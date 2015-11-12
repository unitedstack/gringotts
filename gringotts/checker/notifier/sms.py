from gringotts.checker import notifier
from gringotts.openstack.common import log


LOG = log.getLogger(__name__)


class SMSNotifier(notifier.Notifier):

    @staticmethod
    def notify_has_owed(context, account, contact, projects, **kwargs):
        pass

    @staticmethod
    def notify_before_owed(context, account, contact, projects, price_per_day, days_to_owe, **kwargs):
        pass

    @staticmethod
    def notify_account_charged(context, account, contact, type, value, bonus=None, **kwargs):
        pass

    @staticmethod
    def notify_order_billing_owed(context, account, contact, order, **kwargs):
        pass

