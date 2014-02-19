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
from gringotts import utils as gringutils

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

    def _order(self, start_time=None, end_time=None):
        self.conn = pecan.request.db_conn
        try:
            order = self.conn.get_bills_by_order_id(request.context,
                                                    order_id=self._id,
                                                    start_time=start_time,
                                                    end_time=end_time)
        except Exception as e:
            LOG.error('Order(%s)\'s bills not found' % self._id)
            raise exception.OrderBillsNotFound(order_id=self._id)
        return order

    @wsexpose([models.Bill], wtypes.text, datetime.datetime, datetime.datetime)
    def get(self, start_time=None, end_time=None):
        """Return this order's detail
        """
        bills = self._order(start_time=start_time, end_time=end_time)
        return [models.Bill.from_db_model(bill) for bill in bills]


class SummaryController(rest.RestController):
    """Summary every order type's consumption
    """
    @wsexpose(models.Summaries, datetime.datetime, datetime.datetime)
    def get(self, start_time=None, end_time=None):
        """Get summary of all kinds of orders
        """
        conn = pecan.request.db_conn

        # Get all orders of this particular context one time
        orders_db = list(conn.get_orders(request.context,
                                         start_time=start_time,
                                         end_time=end_time))

        total_price = gringutils._quantize_decimal(0)
        total_count = 0
        summaries = []

        # loop all order types
        for order_type in ORDER_TYPE:

            order_total_price = gringutils._quantize_decimal(0)
            order_total_count = 0

            # One user's order records will not be very large, so we can
            # traverse them directly
            for order in orders_db:
                if order.type != order_type:
                    continue
                price, count = self._get_order_price_and_count(order,
                                                               start_time=start_time,
                                                               end_time=end_time)
                order_total_price += price
                order_total_count += count

            summaries.append(models.Summary.transform(total_count=order_total_count,
                                                      order_type=order_type,
                                                      total_price=order_total_price))
            total_price += order_total_price
            total_count += order_total_count

        return models.Summaries.transform(total_price=total_price,
                                          total_count=total_count,
                                          summaries=summaries)

    def _get_order_price_and_count(self, order,
                                   start_time=None, end_time=None):

        if not all([start_time, end_time]):
            return (order.total_price, 1)

        conn = pecan.request.db_conn
        total_price = conn.get_bills_sum(request.context,
                                         start_time=start_time,
                                         end_time=end_time,
                                         order_id=order.order_id)
        if total_price:
            return (total_price, 1)
        else:
            return (total_price, 0)


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

    @wsexpose(models.Orders, wtypes.text, wtypes.text, datetime.datetime,
              datetime.datetime)
    def get_all(self, type=None, status=None, start_time=None, end_time=None):
        """Get queried orders
        If start_time and end_time is not None, will get orders that have bills
        during start_time and end_time, or return all orders directly.
        """
        conn = pecan.request.db_conn
        orders_db = list(conn.get_orders(request.context,
                                         type=type,
                                         status=status,
                                         start_time=start_time,
                                         end_time=end_time))
        orders = []
        total_count = len(orders_db)
        total_price = gringutils._quantize_decimal(0)

        for order in orders_db:
            price = self._get_order_price(order,
                                          start_time=start_time,
                                          end_time=end_time)
            total_price += price
            order.total_price = price
            orders.append(models.Order.from_db_model(order))

        return models.Orders.transform(total_count=total_count,
                                       total_price=total_price,
                                       orders=orders)

    def _get_order_price(self, order, start_time=None, end_time=None):
        if not all([start_time, end_time]):
            return order.total_price

        conn = pecan.request.db_conn
        total_price = conn.get_bills_sum(request.context,
                                         start_time=start_time,
                                         end_time=end_time,
                                         order_id=order.order_id)
        return total_price
