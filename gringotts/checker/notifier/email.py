# -*- coding: utf-8 -*-

from gringotts import notifier as gring_notifier

from gringotts.checker import notifier
from gringotts.openstack.common import log
from gringotts.openstack.common.gettextutils import _


LOG = log.getLogger(__name__)


class EmailNotifier(notifier.Notifier):

    @staticmethod
    def notify_has_owed(context, account, contact, orders):
        # Get account info
        account_name = contact.get('real_name') or contact['email'].split('@')[0]
        mobile_number = contact.get('mobile_number') or "unknown"
        company = contact.get('company') or "unknown"

        # Notify user
        resources = 'resources' if len(orders) > 1 else 'resource'
        subject = u"[UnitedStack] 您好, %s, 您有%s个资源已经欠费" % (account_name, len(orders))
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

        # Notify us
        subject = u"[UnitedStack] 用户[%s]已欠费，电话[%s]，公司[%s]" % \
                (account_name, mobile_number, company)
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
                    'to': 'support@unitedstack.com'
                }
            }
        }
        notify = gring_notifier.get_notifier(service='checker')
        notify.info(context, 'uos.account.owed', payload)

    @staticmethod
    def notify_before_owed(context, account, contact, price_per_day, days_to_owe):
        # Get account info
        account_name = contact.get('real_name') or contact['email'].split('@')[0]
        mobile_number = contact.get('mobile_number') or "unknown"
        company = contact.get('company') or "unknown"

        # Notify user
        subject = u"[UnitedStack] 您好, %s, 您的账户余额不足, 请及时充值" % account_name
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

        # Notify us
        subject = u"[UnitedStack] 用户[%s]的账户余额即将不足，电话[%s]，公司[%s]" % \
                (account_name, mobile_number, company)
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
                    'to': 'support@unitedstack.com'
                }
            }
        }
        notify = gring_notifier.get_notifier(service='checker')
        notify.info(context, 'uos.account.will_owed', payload)

    @staticmethod
    def notify_account_charged(context, account, contact, value, bonus=None):
        # Notify user
        subject = u"[UnitedStack] 您好, %s, 您已充值成功" % contact['email'].split('@')[0]
        payload = {
            'actions': {
                'email': {
                    'template': 'charge_to_user',
                    'context': {
                        'value': str(value),
                        'balance': str(account['balance']),
                        'bonus': str(bonus),
                    },
                    'subject': subject,
                    'from': 'noreply@unitedstack.com',
                    'to': contact['email']
                }
            }
        }
        notify = gring_notifier.get_notifier(service='checker')
        notify.info(context, 'uos.account.charged', payload)

        # Notify us
        subject = u"[UnitedStack] 账户[%s]充值[￥%s]" % (contact['email'].split('@')[0], value)
        payload = {
            'actions': {
                'email': {
                    'template': 'charge_to_admin',
                    'context': {
                        'email': contact['email'],
                        'value': str(value),
                        'balance': str(account['balance']),
                        'bonus': str(bonus),
                    },
                    'subject': subject,
                    'from': 'noreply@unitedstack.com',
                    'to': 'support@unitedstack.com'
                }
            }
        }
        notify = gring_notifier.get_notifier(service='checker')
        notify.info(context, 'uos.account.charged', payload)
