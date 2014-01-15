import calendar
import pecan
import wsme
import datetime

from pecan import rest
from pecan import request
from wsmeext.pecan import wsexpose
from wsme import types as wtypes

from oslo.config import cfg

from gringotts import exception
from gringotts.api.v1 import models
from gringotts.db import models as db_models
from gringotts.openstack.common import log
from gringotts.openstack.common import uuidutils


LOG = log.getLogger(__name__)


ORDER_TYPE = ['instance', 'image', 'snapshot', 'volume', 'router',
              'loadbalancer', 'floatingip', 'vpn']


class OrderController(rest.RestController):
    """For one single order, getting its detail consumptions
    """
    def __init__(self, order_id):
        self._id = order_id

    def _order(self):
        self.conn = pecan.request.db_conn
        try:
            order = self.conn.get_bills_by_order_id(request.context,
                                                    order_id=self._id)
        except Exception as e:
            LOG.error('Order(%s)\'s bills not found' % self._id)
            raise exception.OrderBillsNotFound(order_id=self._id)
        return order

    @wsexpose([models.Bill], wtypes.text)
    def get(self):
        """Return this order's detail
        """
        bills = self._order()
        return [models.Bill.from_db_model(bill) for bill in bills]


class SummaryController(rest.RestController):
    """Summary every order type's consumption
    """
    @wsexpose(models.Summaries)
    def get(self):
        """Get summary of all kinds of orders
        """
        conn = pecan.request.db_conn

        # Get all orders of this particular context one time
        orders_db = list(conn.get_orders(request.context))

        total_price = 0
        summaries = []

        # loop all order types
        for order_type in ORDER_TYPE:

            order_total_price = 0
            quantity = 0

            # One user's order records will not be very large, so we can
            # traverse them directly
            for order in orders_db:
                if order.type != order_type:
                    continue
                order_total_price += order.total_price
                quantity += 1

            summaries.append(models.Summary.transform(quantity=quantity,
                                                      order_type=order_type,
                                                      total_price=order_total_price))
            total_price += order_total_price

        return models.Summaries.transform(total_price=total_price,
                                          summaries=summaries)


class OrdersController(rest.RestController):
    """The controller of resources
    """
    summary = SummaryController()

    @pecan.expose()
    def _lookup(self, order_id, *remainder):
        if remainder and not remainder[-1]:
            remainder = remainder[:-1]
        if uuidutils.is_uuid_like(order_id):
            return OrderController(order_id), remainder

    @wsexpose(models.Orders, wtypes.text)
    def get_all(self, type=None):
        """Get all orders, filter by type
        """
        conn = pecan.request.db_conn

        orders_db = list(conn.get_orders(request.context, type=type))

        orders = []
        order_amount = len(orders_db)
        total_price = 0

        for order in orders_db:
            total_price += order.total_price
            orders.append(models.Order.from_db_model(order))

        return models.Orders.transform(order_amount=order_amount,
                                       total_price=total_price,
                                       orders=orders)
