from gringotts import notifier as gring_notifier

from gringotts.checker import notifier
from gringotts.openstack.common import log
from gringotts.openstack.common.gettextutils import _


LOG = log.getLogger(__name__)


class EmailNotifier(notifier.Notifier):

    @staticmethod
    def notify_has_owed(context, account, contact, orders):
        account_name = contact['email'].split('@')[0]
        resources = 'resources' if len(orders) > 1 else 'resource'
        subject = _('Hello, %s, you have %s %s overdue bills') \
                % (account_name, len(orders), resources)
        payload = {
            'actions': {
                'email': {
                    'template': 'account_has_owed',
                    'context': {
                        'orders': orders,
                        'reserved_days': account['reserved_days']
                    },
                    'subject': subject,
                    'from': 'noreply@unitedstack.com',
                    'to': contact['email']
                }
            }
        }
        notify = gring_notifier.get_notifier(service='checker')
        notify.info(context, 'uos.account.owed', payload)


    @staticmethod
    def notify_before_owed(context, account, contact, price_per_day, days_to_owe):
        subject = _('Hello, %s, your balance is not enough') % contact['email'].split('@')[0]
        payload = {
            'actions': {
                'email': {
                    'template': 'account_will_owe',
                    'context': {
                        'price_per_day': price_per_day,
                        'balance': str(account['balance']),
                        'days_to_owe': days_to_owe
                    },
                    'subject': subject,
                    'from': 'noreply@unitedstack.com',
                    'to': contact['email']
                }
            }
        }
        notify = gring_notifier.get_notifier(service='checker')
        notify.info(context, 'uos.account.will_owed', payload)
