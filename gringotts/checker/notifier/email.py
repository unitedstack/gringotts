# -*- coding: utf-8 -*-

from gringotts import notifier as gring_notifier

from gringotts.checker import notifier
from gringotts.openstack.common import log
from gringotts.openstack.common.gettextutils import _


LOG = log.getLogger(__name__)


class EmailNotifier(notifier.Notifier):

    @staticmethod
    def notify_has_owed(context, account, contact, projects):
        # Get account info
        account_name = contact.get('real_name') or contact['email'].split('@')[0]
        mobile_number = contact.get('mobile_number') or "unknown"
        company = contact.get('company') or "unknown"

        # Notify user
        order_count = 0
        for project in projects:
            order_count += len(project['orders'])

        subject = u"[UnitedStack] 您好, %s, 您有%s个资源已经欠费" % (account_name, order_count)
        payload = {
            'actions': {
                'email': {
                    'template': 'account_has_owed',
                    'context': {
                        'send_to': 'user',
                        'projects': projects,
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
                        'send_to': 'uos',
                        'real_name': account_name,
                        'mobile': mobile_number,
                        'email': contact['email'],
                        'company': company,
                        'projects': projects,
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
    def notify_before_owed(context, account, contact, projects, price_per_day, days_to_owe):
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
                        'send_to': 'user',
                        'projects': projects,
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
                        'send_to': 'uos',
                        'real_name': account_name,
                        'mobile': mobile_number,
                        'email': contact['email'],
                        'company': company,
                        'projects': projects,
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
    def notify_account_charged(context, account, contact, type, value, bonus=None):
        # Notify user
        account_name = contact.get('real_name') or contact['email'].split('@')[0]
        if type == 'bonus':
            subject = u"[UnitedStack] 您好，%s，系统为您充值[￥%s]" % (account_name, value)
        else:
            subject = u"[UnitedStack] 您好, %s, 您已充值成功" % account_name
        payload = {
            'actions': {
                'email': {
                    'template': 'charge_to_user',
                    'context': {
                        'type': type,
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
        if type == 'bonus':
            subject = u"[UnitedStack] 系统为用户[%s]充值[￥%s]" % (account_name, value)
        else:
            subject = u"[UnitedStack] 用户[%s]成功充值[￥%s]" % (account_name, value)
        payload = {
            'actions': {
                'email': {
                    'template': 'charge_to_admin',
                    'context': {
                        'type': type,
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
