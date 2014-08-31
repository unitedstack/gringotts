#!/usr/bin/python
"""Handle user registeration
"""
from decimal import Decimal
from oslo.config import cfg

from gringotts import context
from gringotts import db
from gringotts.db import models as db_models
from gringotts import exception
from gringotts import plugin
from gringotts.waiter import plugin as waiter_plugin

from gringotts.openstack.common import log


LOG = log.getLogger(__name__)


OPTS = [
    cfg.StrOpt('keystone_control_exchange',
               default='keystone',
               help="Exchange name for Keystone notifications"),
]


cfg.CONF.register_opts(OPTS)

db_conn = db.get_connection(cfg.CONF)


class RegisterNotificationBase(waiter_plugin.NotificationBase):
    @staticmethod
    def get_exchange_topics(conf):
        """Return a sequence of ExchangeTopics defining the exchange and
        topics to be connected for this plugin.
        """
        return [
            plugin.ExchangeTopics(
                exchange=conf.keystone_control_exchange,
                topics=set(topic + ".info"
                           for topic in conf.notification_topics)),
        ]

    def make_order(self, message):
        raise NotImplementedError()


class UserRegisterEnd(RegisterNotificationBase):
    """Handle the event that user registers
    """
    event_types = ['identity.account.register']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s, user_id: %s',
                  message['event_type'], message['payload']['user_id'])
        # create account
        try:
            user_id = message['payload']['user_id']
            project_id = message['payload']['project_id'] # default project id
            domain_id = message['payload']['domain_id']
            balance = '0'
            consumption = '0'
            level = cfg.CONF.waiter.initial_level
            self.create_account(user_id, domain_id, balance, consumption,
                                level, project_id=project_id)
        except Exception:
            LOG.exception('Fail to create account %s for the domain %s' % \
                    (user_id, domain_id))
            raise exception.AccountCreateFailed(user_id=user_id, domain_id=domain_id)

        # charge account
        try:
            type = 'bonus'
            come_from = 'system'
            bonus = message['payload'].get('bonus', cfg.CONF.waiter.initial_balance)
            self.charge_account(user_id, str(bonus), type, come_from)
        except Exception:
            LOG.exception('Fail to charge %s to account %s' % (initial_level, user_id))
            raise exception.AccountChargeFailed(balance=initial_balance, user_id=user_id)

        LOG.info('Create user %s for the domain %s successfully' % (user_id, domain_id))

        # create project and user_project
        try:
            user_id = message['payload']['user_id']
            project_id = message['payload']['project_id']
            domain_id = message['payload']['domain_id']
            consumption = '0'
            self.create_project(user_id, project_id, domain_id, consumption)
        except Exception:
            LOG.exception('Fail to create project %s with project_owner %s' % \
                    (project_id, user_id))
            raise exception.ProjectCreateFaild(project_id=project_id,
                                               user_id=user_id)

        LOG.info('Create project %s with project_owner %s successfully' % (project_id, user_id))


class UserCreatedEnd(RegisterNotificationBase):
    """Handle the event that user be created"""

    event_types = ['identity.user.create']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s, user_id: %s',
                  message['event_type'], message['payload']['user_id'])
        # create account
        try:
            user_id = message['payload']['user_id']
            domain_id = message['payload']['domain_id']
            balance = '0'
            consumption = '0'
            level = cfg.CONF.waiter.user_initial_level
            self.create_account(user_id, domain_id, balance, consumption, level)
        except Exception:
            LOG.exception('Fail to create account %s for the domain %s' % \
                    (user_id, domain_id))
            raise exception.AccountCreateFailed(user_id=user_id, domain_id=domain_id)

        # charge account
        try:
            type = 'bonus'
            come_from = 'system'
            bonus = message['payload'].get('bonus', cfg.CONF.waiter.user_initial_balance)
            if float(bonus) > 0:
                self.charge_account(user_id, bonus, type, come_from)
        except Exception:
            LOG.exception('Fail to charge %s to account %s' % (bonus, user_id))
            raise exception.AccountChargeFailed(value=bonus, user_id=user_id)

        LOG.info('Create account %s for the domain %s successfully' % (user_id, domain_id))


class ProjectCreatedEnd(RegisterNotificationBase):
    """Handle the event that project be created"""

    event_types = ['identity.project.create']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s, project_id: %s',
                  message['event_type'], message['payload']['project_id'])
        try:
            user_id = message['payload']['billing_owner_id']
            project_id = message['payload']['project_id']
            domain_id = message['payload']['domain_id']
            consumption = '0'
            self.create_project(user_id, project_id, domain_id, consumption)
        except Exception:
            LOG.exception('Fail to create project %s with project_owner %s' % \
                    (project_id, user_id))
            raise exception.ProjectCreateFaild(project_id=project_id,
                                               user_id=user_id)

        LOG.info('Create project %s with billling_owner %s successfully' % (project_id, user_id))


class ProjectDeletedEnd(RegisterNotificationBase):
    """Handle the event that project be deleted"""

    event_types = ['identity.project.delete']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s, project_id: %s',
                  message['event_type'], message['payload']['project_id'])
        try:
            project_id = message['payload']['project_id']
            self.delete_resources(project_id)
        except Exception:
            LOG.exception('Fail to delete all resources of project %s' % project_id)
            return

        LOG.info('Delete all resources of project %s successfully' % project_id)


class BillingOwnerChangedEnd(RegisterNotificationBase):
    """Handle the event that billing owner changed"""

    event_types = ['identity.billing_owner.changed']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s, project_id: %s',
                  message['event_type'], message['payload']['project_id'])
        try:
            project_id = message['payload']['project_id']
            user_id = message['payload']['billing_owner_id']
            self.change_billing_owner(project_id, user_id)
        except Exception:
            LOG.exception('Fail to change billing owner of project %s to user %s' % (project_id, user_id))
            return

        LOG.info('Change billing owner of project %s to user %s successfully' % (project_id, user_id))
