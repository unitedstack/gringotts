import calendar
import pecan
import wsme
import datetime

from dateutil.relativedelta import relativedelta

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


class TrendsController(rest.RestController):
    """Summary every order type's consumption
    """
    @wsexpose(models.Summaries)
    def get(self):
        """Get summary of all kinds of orders in the last year
        """
        conn = pecan.request.db_conn
        orders_db = conn.get_orders(request.context)

        # The last 12 months from now
        now = datetime.datetime.utcnow()
        first_day = datetime.datetime(now.year, now.month, 1)

        12_months = [(first_day, now)]

        for i in range(12):
            start_month = first_day - relativedelta(months=i+1)
            month_day = calendar.monthrange(start_month.year, start_month.month)[1]
            end_month = start_month + datetime.timedelta(days=month_day-1)
            12_months.append((start_month, end_month))


class OrdersController(rest.RestController):
    """The controller of resources
    """
    summary = SummaryController()
    trends = TrendsController()

    @pecan.expose()
    def _lookup(self, order_id, *remainder):
        if remainder and not remainder[-1]:
            remainder = remainder[:-1]
        if uuidutils.is_uuid_like(order_id):
            return OrderController(order_id), remainder

    @wsexpose(models.Orders, wtypes.text, wtypes.text, wtypes.text)
    def get_all(self, start_time=None, end_time=None, type=None):
        """Get all orders, filter by start_time, end_time, type
        """
        conn = pecan.request.db_conn

        orders_db = list(conn.get_orders(request.context,
                                         start_time=start_time,
                                         end_time=end_time,
                                         type=type))

        orders = []
        order_amount = len(orders_db)

        for order in orders_db:
            orders.append(models.Order.from_db_model(order))

        return models.Orders.transform(order_amount=order_amount,
                                       orders=orders)
