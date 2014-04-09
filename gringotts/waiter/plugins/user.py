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
    """Handle the event that volume be created
    """
    event_types = ['identity.account.register']

    def process_notification(self, message):
        LOG.debug('Do action for event: %s, tenant_id: %s',
                  message['event_type'], message['payload']['project_id'])

        try:
            user_id = message['payload']['user_id']
            project_id = message['payload']['project_id']
            balance = cfg.CONF.waiter.initial_balance
            consumption = '0'
            currency = 'CNY'
            level = cfg.CONF.waiter.initial_level
            self.create_account(user_id, project_id, balance,
                                consumption, currency, level)
        except Exception:
            LOG.exception('Fail to create account for the project: %s' %
                          project_id)
            raise exception.AccountCreateFailed(project_id=project_id)
        LOG.debug('Create account for the project %s successfully' % project_id)
