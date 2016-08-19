# -*- coding: utf-8 -*-

from gringotts import notifier as gring_notifier

from oslo_config import cfg

from gringotts.checker import notifier
from gringotts.openstack.common import log
from gringotts.openstack.common.gettextutils import _


LOG = log.getLogger(__name__)


class EmailNotifier(notifier.Notifier):

    @staticmethod
    def notify_has_owed(context, account, contact, projects, **kwargs):
        # TODO(chengkun): Now we can't get user contact info,
        # and it will be "unknown". we will add in the future
        account_name = contact.get('real_name') or contact['email'].split('@')[0]
        mobile_number = contact.get('mobile_number') or "unknown"
        company = contact.get('company') or "unknown"

        # Notify user
        order_count = 0
        for project in projects:
            order_count += len(project['orders'])

        payload = {
            'actions': {
                'email': {
                    'email_template': 'billing/account_has_owed',
                    'context': {
                        'send_to': 'user',
                        'account_name': account_name,
                        'projects': projects,
                        'reserved_days': account['reserved_days'],
                        'order_count': order_count,
                        'recharge_url': cfg.CONF.checker.recharge_url,
                        'language': kwargs.get('language'),
                    },
                    'from': 'noreply@unitedstack.com',
                    'to': contact['email']
                }
            }
        }
        notify = gring_notifier.get_notifier(service='checker')
        notify.info(context, 'uos.account.owed', payload)

        # Notify us
        if cfg.CONF.checker.support_email:
            payload = {
                'actions': {
                    'email': {
                        'email_template': 'billing/account_has_owed',
                        'context': {
                            'send_to': 'uos',
                            'cloud_name': cfg.CONF.cloud_name,
                            'account_name': account_name,
                            'mobile': mobile_number,
                            'email': contact['email'],
                            'company': company,
                            'projects': projects,
                            'reserved_days': account['reserved_days'],
                            'language': kwargs.get('language'),
                        },
                        'from': 'noreply@unitedstack.com',
                        'to': cfg.CONF.checker.support_email
                    }
                }
            }
            notify = gring_notifier.get_notifier(service='checker')
            notify.info(context, 'uos.account.owed', payload)

    @staticmethod
    def notify_before_owed(context, account, contact, projects, price_per_day, days_to_owe, **kwargs):
        # Get account info
        account_name = contact.get('real_name') or contact['email'].split('@')[0]
        mobile_number = contact.get('mobile_number') or "unknown"
        company = contact.get('company') or "unknown"

        # Notify user
        payload = {
            'actions': {
                'email': {
                    'email_template': 'billing/account_will_owe',
                    'context': {
                        'send_to': 'user',
                        'account_name': account_name,
                        'projects': projects,
                        'price_per_day': price_per_day,
                        'balance': str(account['balance']),
                        'days_to_owe': days_to_owe,
                        'recharge_url': cfg.CONF.checker.recharge_url,
                        'language': kwargs.get('language'),
                    },
                    'from': 'noreply@unitedstack.com',
                    'to': contact['email']
                }
            }
        }
        notify = gring_notifier.get_notifier(service='checker')
        notify.info(context, 'uos.account.will_owed', payload)

        # Notify us
        if cfg.CONF.checker.support_email:
            payload = {
                'actions': {
                    'email': {
                        'email_template': 'billing/account_will_owe',
                        'context': {
                            'send_to': 'uos',
                            'cloud_name': cfg.CONF.cloud_name,
                            'account_name': account_name,
                            'mobile': mobile_number,
                            'email': contact['email'],
                            'company': company,
                            'projects': projects,
                            'price_per_day': price_per_day,
                            'balance': str(account['balance']),
                            'days_to_owe': days_to_owe,
                            'language': kwargs.get('language'),
                        },
                        'from': 'noreply@unitedstack.com',
                        'to': cfg.CONF.checker.support_email
                    }
                }
            }
            notify = gring_notifier.get_notifier(service='checker')
            notify.info(context, 'uos.account.will_owed', payload)

    @staticmethod
    def notify_order_billing_owed(context, account, contact, order,**kwargs):
        """Only notify for user with has_owed or will_owed order
        """
        # Get account info
        account_name = contact.get('real_name') or contact['email'].split('@')[0]

        # Notify user
        payload = {
            'actions': {
                'email': {
                    'email_template': 'billing/order_billing_owed',
                    'context': {
                        'send_to': 'user',
                        'account_name': account_name,
                        'order': order,
                        'email': contact['email'],
                        'balance': str(account['balance']),
                        'order_recharge_url': cfg.CONF.checker.order_recharge_url,
                        'language': kwargs.get('language'),
                        'reserved_days': account['reserved_days'],
                    },
                    'from': 'noreply@unitedstack.com',
                    'to': contact['email']
                }
            }
        }
        notify = gring_notifier.get_notifier(service='checker')
        notify.info(context, 'uos.account.order_billing_owed', payload)

    @staticmethod
    def notify_account_charged(context, account, contact, type, value, bonus=None, **kwargs):
        account_name = contact.get('real_name') or contact['email'].split('@')[0]
        mobile_number = contact.get('mobile_number') or "unknown"
        company = contact.get('company') or "unknown"

        # Notify user
        payload = {
            'actions': {
                'email': {
                    'email_template': 'billing/charge_to_user',
                    'context': {
                        'type': type,
                        'account_name': account_name,
                        'value': str(value),
                        'balance': str(account['balance']),
                        'bonus': str(bonus),
                        'language': kwargs.get('language'),
                    },
                    'from': 'noreply@unitedstack.com',
                    'to': contact['email']
                }
            }
        }
        notify = gring_notifier.get_notifier(service='checker')
        notify.info(context, 'uos.account.charged', payload)

        # Notify us
        if cfg.CONF.checker.support_email:
            payload = {
                'actions': {
                    'email': {
                        'email_template': 'billing/charge_to_admin',
                        'context': {
                            'type': type,
                            'cloud_name': cfg.CONF.cloud_name,
                            'account_name': account_name,
                            'mobile': mobile_number,
                            'company': company,
                            'operator_name': kwargs.get('operator_name'),
                            'operator': kwargs.get('operator'),
                            'remarks': kwargs.get('remarks'),
                            'email': contact['email'],
                            'value': str(value),
                            'balance': str(account['balance']),
                            'bonus': str(bonus),
                            'language': kwargs.get('language'),
                        },
                        'from': 'noreply@unitedstack.com',
                        'to': cfg.CONF.checker.support_email
                    }
                }
            }
            notify = gring_notifier.get_notifier(service='checker')
            notify.info(context, 'uos.account.charged', payload)

    @staticmethod
    def send_account_info(context, account_infos, email_addr_name):
        for key, value in email_addr_name.items():
            payload = {
                'actions': {
                    'email': {
                        'email_template': 'to_sales/accounts_consumption_info',
                        'context': {
                            'content': value[1],
                        },
                        'file_data': account_infos[value[0]],
                        'to': value[0],
                    }
                }
            }
            notify = gring_notifier.get_notifier(service='lotus-collector')
            notify.info(context, 'uos.notification.email_attachment', payload)
