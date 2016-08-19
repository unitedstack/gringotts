#!/usr/bin/env python
# encoding: utf-8
import abc
import copy
import functools
import six

from oslo_config import cfg
from stevedore import extension

from gringotts.client import client
from gringotts import constants as const
from gringotts.openstack.common import uuidutils
from gringotts.price import pricing
from gringotts.services import keystone as ks_client
from gringotts.services import register_class


CONF = cfg.CONF

GCLIENT = client.get_client()

RESOURCE_SERVICE_TYPE = ['network', 'network', 'network',
                         'compute', 'volume', 'volume', 'image']
RESOURCE = ['floatingip', 'router', 'listener', 'instance',
            'volume', 'snapshot', 'image']

register_class = functools.partial(register_class, ks_client)

class Resource(object):

    """TODO(chengkun): Maybe put it in public area?  """

    def __init__(self, resource_id, resource_name, type, status,
                 user_id, project_id):
        self.resource_id = resource_id
        self.resource_name = resource_name
        self.type = type
        self.status = status
        self.user_id = user_id
        self.project_id = project_id

    def as_dict(self):
        """Make Variables to a dict.
        :returns: dict of Variables

        """
        return copy.copy(self.__dict__)


@six.add_metaclass(abc.ABCMeta)
class CheckBase(object):

    """Base check class. """

    @abc.abstractproperty
    def product_items(self):
        pass

    def create_order(self, resource, unit='hour', period=None, renew=None):
        """Create order for resource. """
        order_id = uuidutils.generate_uuid()
        parsed_resource = self.parse_resource(resource)
        unit_price = self.get_unit_price(resource, method=unit)

        for ext in self.product_items.extensions:
            state = ext.name.split('_')[0]
            ext.obj.create_subscription(resource.to_env(), resource.to_body(),
                                        order_id, type=state)

        GCLIENT.create_order(order_id,
                             CONF.region_name,
                             unit_price,
                             unit,
                             period=period,
                             renew=renew,
                             **parsed_resource.as_dict())

    def get_unit_price(self, resource, method):
        """Caculate unit price of this order.

        :method: method of bill, now we support hour bill
        :returns: unit price

        """
        unit_price = 0
        for ext in self.product_items.extensions:
            if ext.name.startswith('running'):
                price = ext.obj.get_unit_price(resource.to_env(),
                                               resource.to_body(), method)
                unit_price += price
        return unit_price

    def change_unit_price(self, resource, status, order_id):
        pass

    def change_order_unit_price(self,  order_id, quantity, status):
        """Change the order's subscriptions and unit price.

        :order_id: TODO
        :quantity: TODO
        :status: TODO

        """

        # change subscirption's quantity
        GCLIENT.change_subscription(order_id, quantity, status)

        # change the order's unit price
        GCLIENT.change_order(order_id, status)

    def change_flavor_unit_price(self,  order_id, new_flavor,
                                 service, region_id, status):
        """Just change the unit price that may changes,
        so we only consider the flavor.

        :order_id: TODO
        :new_flavor: TODO
        :service: TODO
        :region_id: TODO
        :status: TODO

        """

        if status == const.STATE_RUNNING:
            # change subscirption's quantity
            GCLIENT.change_flavor_subscription(order_id, new_flavor, None,
                                               service, region_id, status)
        # change the order's unit price
        GCLIENT.change_order(order_id, status)

    def parse_resource(self, resource):
        """parse resource to Resource obj.

        :resource: origin resource
        :returns: Resource object

        """
        return Resource(resource_id=resource.id,
                        resource_name=resource.name,
                        type=resource.resource_type,
                        status=resource.status,
                        user_id=getattr(resource, 'user_id', None),
                        project_id=resource.project_id)


def get_product_items(type):
    return extension.ExtensionManager(
        namespace='gringotts.%s.product_items' % type,
        invoke_on_load=True,
        invoke_args=(GCLIENT,))


class NovaCheck(CheckBase):

    """Docstring for InstanceCheck. """

    product_items = None

    def __init__(self):
        self.product_items = get_product_items('server')

    def change_unit_price(self, resource, status, order_id):
        instance_type = resource.flavor_name

        product_name = '%s:%s' % (const.PRODUCT_INSTANCE_TYPE_PREFIX,
                                  instance_type)
        service = const.SERVICE_COMPUTE
        region_id = CONF.region_name
        self.change_flavor_unit_price(order_id, product_name,
                                      service, region_id, status)


class NeutronCheck(CheckBase):

    """Docstring for NeutronCheck. """

    product_items = {}

    def __init__(self):
        for name in ['floatingip', 'router', 'listener']:
            self.product_items[name] = get_product_items(name)

    def create_order(self, resource, unit='hour', period=None, renew=None):
        """Create order for resource. """
        order_id = uuidutils.generate_uuid()
        parsed_resource = self.parse_resource(resource)
        unit_price = self.get_unit_price(resource, method=unit)

        for ext in self.product_items[resource.resource_type].extensions:
            state = ext.name.split('_')[0]
            ext.obj.create_subscription(resource.to_env(), resource.to_body(),
                                        order_id, type=state)

        GCLIENT.create_order(order_id, CONF.region_name,
                             unit_price, period=period,
                             renew=renew, **parsed_resource.as_dict)

    def get_unit_price(self, resource, method):
        unit_price = 0
        for ext in self.product_items[resource.resource_type].extensions:
            if ext.name.startswith('running'):
                price = ext.obj.get_unit_price(resource.to_env(),
                                               resource.to_body(), method)
                unit_price += price
        return unit_price

    def change_unit_price(self, resource, status, order_id):
        quantity = None
        if resource.resource_type == const.RESOURCE_LISTENER:
           quantity = int(resource.connection_limit) / 1000
        elif resource.resource_type == const.RESOURCE_FLOATINGIP:
            quantity = pricing.rate_limit_to_unit(resource.size)

        if quantity is not None:
            self.change_order_unit_price(order_id, quantity, status)


class GlanceCheck(CheckBase):

    """Docstring for GlanceCheck. """

    product_items = None

    def __init__(self):
        self.product_items = get_product_items('snapshot')


class CinderCheck(CheckBase):

    """Docstring for CinderCheck. """

    product_items = None

    def __init__(self):
        self.product_items = get_product_items('volume')

    def change_unit_price(self, resource, status, order_id):
        quantity = resource.size
        self.change_order_unit_price(order_id, quantity, status)


CLASS_REGISTER = [NeutronCheck, NeutronCheck, NeutronCheck,
                  NovaCheck, CinderCheck, CinderCheck, GlanceCheck]

map(register_class, RESOURCE_SERVICE_TYPE, RESOURCE, CLASS_REGISTER)
