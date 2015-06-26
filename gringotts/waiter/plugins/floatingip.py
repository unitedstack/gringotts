#!/usr/bin/python
# -*- coding: utf-8 -*-

"""Plugins for executing specific actions acrronding to notification events.
"""

from datetime import datetime
from datetime import timedelta

from oslo.config import cfg
from stevedore import extension

from gringotts import constants as const
from gringotts import utils as gringutils
from gringotts import context
from gringotts import plugin
from gringotts.waiter import plugin as waiter_plugin
from gringotts.waiter.plugin import Collection
from gringotts.waiter.plugin import Order
from gringotts import services
from gringotts.services import lotus
from gringotts.services import keystone as ks_client

from gringotts.openstack.common import log
from gringotts.openstack.common import uuidutils
from gringotts.openstack.common import jsonutils


LOG = log.getLogger(__name__)


OPTS = [
    cfg.StrOpt('neutron_control_exchange',
               default='neutron',
               help="Exchange name for Neutron notifications"),
]


cfg.CONF.register_opts(OPTS)


class RateLimitItem(waiter_plugin.ProductItem):

    def get_collection(self, message):
        """Get collection from message
        """
        product_name = const.PRODUCT_FLOATINGIP
        service = const.SERVICE_NETWORK
        region_id = cfg.CONF.region_name
        resource_id = message['payload']['floatingip']['id']
        resource_name = message['payload']['floatingip']['uos:name']
        resource_type = const.RESOURCE_FLOATINGIP
        resource_volume = int(message['payload']['floatingip']['rate_limit']) / 1024
        user_id = None
        project_id = message['payload']['floatingip']['tenant_id']

        return Collection(product_name=product_name,
                          service=service,
                          region_id=region_id,
                          resource_id=resource_id,
                          resource_name=resource_name,
                          resource_type=resource_type,
                          resource_volume=resource_volume,
                          user_id=user_id,
                          project_id=project_id)

    @staticmethod
    def calculate_price(quantity, unit_price, price_data=None):
        if price_data and 'type' in price_data:
            if 'base_price' in price_data:
                base_price = gringutils._quantize_decimal(
                    price_data['base_price'])
            else:
                base_price = gringutils._quantize_decimal(0)

            if price_data['type'] == 'segmented' \
                    and 'segmented' in price_data:
                # using segmented price
                # price list is a descendent list has elements of the form:
                #     [(quantity_level)int, (unit_price)int/float]
                q = int(quantity)
                total_price = gringutils._quantize_decimal(0)
                for p in price_data['segmented']:
                    if q > p[0]:
                        total_price += \
                            (q - p[0]) * gringutils._quantize_decimal(p[1])
                        q = p[0]

                return total_price + base_price

        unit_price = gringutils._quantize_decimal(unit_price)
        return unit_price * int(quantity)

    def get_unit_price(self, message):
        c = self.get_collection(message)
        product = self.worker_api.get_product(
            context.get_admin_context(),
            c.product_name, c.service, c.region_id)

        if product:
            price_data = None
            if 'extra' in product and product['extra']:
                try:
                    extra_data = jsonutils.loads(product['extra'])
                    price_data = extra_data.get('price', None)
                except (Exception):
                    LOG.warning('Decode product["extra"] failed')

            return self.calculate_price(
                c.resource_volume, product['unit_price'], price_data)
        else:
            return 0


class FloatingIpNotificationBase(waiter_plugin.NotificationBase):

    def __init__(self):
        super(FloatingIpNotificationBase, self).__init__()
        self.product_items = extension.ExtensionManager(
            namespace='gringotts.floatingip.product_item',
            invoke_on_load=True,
        )

    @staticmethod
    def get_exchange_topics(conf):
        """Return a sequence of ExchangeTopics defining the exchange and
        topics to be connected for this plugin.
        """
        return [
            plugin.ExchangeTopics(
                exchange=conf.neutron_control_exchange,
                topics=set(topic + ".info"
                           for topic in conf.notification_topics)),
        ]

    def make_order(self, message, state=None):
        """Make an order model for one floating ip
        """
        resource_id = message['payload']['floatingip']['id']
        resource_name = message['payload']['floatingip']['uos:name']
        user_id = None
        project_id = message['payload']['floatingip']['tenant_id']

        order = Order(resource_id=resource_id,
                      resource_name=resource_name,
                      type=const.RESOURCE_FLOATINGIP,
                      status=state if state else const.STATE_RUNNING,
                      user_id=user_id,
                      project_id=project_id)
        return order

    def _send_email_notification(self, message):

        def convert_to_localtime(timestamp):
            FORMAT = '%Y-%m-%d %H:%M:%S.%f'
            try:
                # convert from UTC to UTC+8(Beijing)
                dt = datetime.strptime(timestamp, FORMAT) + timedelta(hours=8)
                return dt.strftime(FORMAT[:-3])
            except (ValueError):
                return timestamp

        CTX_TEMPLATE = '_context_%s'

        user_id = message.get(CTX_TEMPLATE % 'user_id')
        if not user_id:
            return

        user = ks_client.get_uos_user(user_id)
        username = user.get('name', '')
        if username == 'doctor':
            return

        event_type = message['event_type']
        if 'create' in event_type:
            event_name = u'创建公网IP'
        elif 'delete' in event_type:
            event_name = u'删除公网IP'
        else:
            return

        content = []
        content.append(u'事件: %s' % (event_name))
        content.append(u'时间: %s' % (
            convert_to_localtime(message['timestamp'])))
        content.append('<hr noshade size=1>')
        content.append(u'项目: %s' % (
            message[CTX_TEMPLATE % 'project_name']))
        content.append(u'用户名: %s' % (username))
        content.append(u'姓名: %s' % (user.get('real_name', '')))
        content.append(u'公司: %s' % (user.get('company', '')))
        content.append(u'Email: %s' % (user.get('email', '')))
        content.append(u'手机号: %s' % (user.get('mobile_number', '')))

        floatingip = message['payload']['floatingip']
        content.append(
            u'公网IP地址: %s' % (floatingip['floating_ip_address']))
        # format of created_at is %Y-%m-%dT%H:%M:%S.%f
        content.append(u'创建时间: %s' % (
            convert_to_localtime(floatingip['created_at'].replace('T', ' '))))

        lotus.send_notification_email(
            u'公网IP变动通知', u'<br />'.join(content))

    def send_email_notification(self, message):
        try:
            self._send_email_notification(message)
        except (Exception) as e:
            # failure of this should not affect accounting function
            LOG.warn('Send email notification failed, %s', e)


class FloatingIpCreateEnd(FloatingIpNotificationBase):
    """Handle the event that floating ip be created
    """
    event_types = ['floatingip.create.end']

    def process_notification(self, message, state=None):
        LOG.warn('Do action for event: %s, resource_id: %s',
                 message['event_type'],
                 message['payload']['floatingip']['id'])

        self.send_email_notification(message)

        # Generate uuid of an order
        order_id = uuidutils.generate_uuid()

        unit_price = 0
        unit = None

        # Create subscriptions for this order
        for ext in self.product_items.extensions:
            if ext.name.startswith('suspend'):
                sub = ext.obj.create_subscription(message, order_id,
                                                  type=const.STATE_SUSPEND)
                if sub and state == const.STATE_SUSPEND:
                    price_data = None
                    if 'extra' in sub and sub['extra']:
                        try:
                            extra_data = jsonutils.loads(sub['extra'])
                            price_data = extra_data.get('price', None)
                        except (Exception):
                            LOG.warning('Decode subscription["extra"] failed')

                    unit_price += RateLimitItem.calculate_price(
                        sub['quantity'], sub['unit_price'], price_data)
                    unit = sub['unit']
            elif ext.name.startswith('running'):
                sub = ext.obj.create_subscription(message, order_id,
                                                  type=const.STATE_RUNNING)
                if sub and (not state or state == const.STATE_RUNNING):
                    price_data = None
                    if 'extra' in sub and sub['extra']:
                        try:
                            extra_data = jsonutils.loads(sub['extra'])
                            price_data = extra_data.get('price', None)
                        except (Exception):
                            LOG.warning('Decode subscription["extra"] failed')

                    unit_price += RateLimitItem.calculate_price(
                        sub['quantity'], sub['unit_price'], price_data)
                    unit = sub['unit']

        # Create an order for this instance
        self.create_order(order_id, unit_price, unit, message, state=state)

        # Notify master, just give master messages it needs
        remarks = 'Floating IP Has Been Created.'
        action_time = message['timestamp']
        if state:
            self.resource_created_again(order_id, action_time, remarks)
        else:
            self.resource_created(order_id, action_time, remarks)

    def get_unit_price(self, message, status, cron_time=None):
        unit_price = 0

        # Create subscriptions for this order
        for ext in self.product_items.extensions:
            if ext.name.startswith(status):
                unit_price += ext.obj.get_unit_price(message)

        return unit_price

    def change_unit_price(self, message, status, order_id):
        quantity = int(message['payload']['floatingip']['rate_limit']) / 1024
        self.change_order_unit_price(order_id, quantity, status)


services.register_class(ks_client,
                        'network',
                        const.RESOURCE_FLOATINGIP,
                        FloatingIpCreateEnd)


class FloatingIpResizeEnd(FloatingIpNotificationBase):
    """Handle the events that floating ip be changed
    """
    event_types = ['floatingip.update_ratelimit.end']

    def process_notification(self, message):
        LOG.warn('Do action for event: %s, resource_id: %s',
                 message['event_type'],
                 message['payload']['floatingip']['id'])

        quantity = int(message['payload']['floatingip']['rate_limit']) / 1024

        # Get the order of this resource
        resource_id = message['payload']['floatingip']['id']
        order = self.get_order_by_resource_id(resource_id)

        # Notify master
        action_time = message['timestamp']
        remarks = 'Floating IP Has Been Resized'
        self.resource_resized(order['order_id'], action_time, quantity, remarks)


class FloatingIpDeleteEnd(FloatingIpNotificationBase):
    """Handle the event that floating ip be deleted
    """
    event_types = ['floatingip.delete.end']

    def process_notification(self, message):
        LOG.warn('Do action for event: %s, resource_id: %s',
                 message['event_type'],
                 message['payload']['floatingip_id'])

        self.send_email_notification(message)

        # Get the order of this resource
        resource_id = message['payload']['floatingip_id']
        order = self.get_order_by_resource_id(resource_id)

        # Notify master
        action_time = message['timestamp']
        remarks = 'Floating IP Has Been Deleted'
        self.resource_deleted(order['order_id'], action_time, remarks)
