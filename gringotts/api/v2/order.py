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

from gringotts.api.v2 import models
from gringotts.db import models as db_models
from gringotts.openstack.common import log
from gringotts.openstack.common import uuidutils


LOG = log.getLogger(__name__)


ORDER_TYPE = ['instance', 'image', 'snapshot', 'volume', 'router',
              'loadbalancer', 'floatingip', 'vpn', 'alarm']


class OrderController(rest.RestController):
    """For one single order, getting its detail consumptions
    """
    def __init__(self, order_id):
        self._id = order_id

    def _order(self, start_time=None, end_time=None,
               limit=None, offset=None):
        self.conn = pecan.request.db_conn
        try:
            bills = self.conn.get_bills_by_order_id(request.context,
                                                    order_id=self._id,
                                                    start_time=start_time,
                                                    end_time=end_time,
                                                    limit=limit,
                                                    offset=offset)
        except Exception as e:
            LOG.error('Order(%s)\'s bills not found' % self._id)
            raise exception.OrderBillsNotFound(order_id=self._id)
        return bills

    @wsexpose(models.Bills, datetime.datetime, datetime.datetime, int, int)
    def get(self, start_time=None, end_time=None, limit=None, offset=None):
        """Return this order's detail
        """
        bills = self._order(start_time=start_time, end_time=end_time,
                            limit=limit, offset=offset)
        bills_list = []
        for bill in bills:
            bills_list.append(models.Bill.from_db_model(bill))

        total_count = self.conn.get_bills_count(request.context,
                                                order_id=self._id,
                                                start_time=start_time,
                                                end_time=end_time)

        return models.Bills.transform(total_count=total_count,
                                      bills=bills_list)


class SummaryController(rest.RestController):
    """Summary every order type's consumption
    """
    @wsexpose(models.Summaries, datetime.datetime, datetime.datetime, wtypes.text,
              wtypes.text, wtypes.text)
    def get(self, start_time=None, end_time=None, region_id=None,
            user_id=None, project_id=None):
        """Get summary of all kinds of orders
        """
        # bad hack
        if not request.context.is_admin and not project_id:
            summaries = []
            for order_type in ORDER_TYPE:
                summaries.append(models.Summary.transform(total_count=0,
                                                          order_type=order_type,
                                                          total_price=gringutils._quantize_decimal(0)))
            return models.Summaries.transform(total_price=gringutils._quantize_decimal(0),
                                              total_count=0,
                                              summaries=summaries)

        conn = pecan.request.db_conn

        # Get all orders of this particular context one time
        orders_db = list(conn.get_orders(request.context,
                                         start_time=start_time,
                                         end_time=end_time,
                                         user_id=user_id,
                                         project_id=project_id,
                                         region_id=region_id))

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


class ResourceController(rest.RestController):
    """Order related to resource
    """
    @wsexpose(models.Order, wtypes.text)
    def get(self, resource_id):
        conn = pecan.request.db_conn
        order = conn.get_order_by_resource_id(request.context,
                                              resource_id)
        return models.Order.from_db_model(order)


class CountController(rest.RestController):
    """Get number of active order
    """
    @wsexpose(int, wtypes.text, bool)
    def get(self, region_id, owed=None):
        conn = pecan.request.db_conn
        order_count = conn.get_active_order_count(request.context,
                                                  region_id=region_id,
                                                  owed=owed)
        return order_count


class StoppedOrderCountController(rest.RestController):
    """Get number of active order
    """
    @wsexpose(int, wtypes.text, bool)
    def get(self, region_id, owed=None):
        conn = pecan.request.db_conn
        order_count = conn.get_stopped_order_count(request.context,
                                                   region_id=region_id,
                                                   owed=owed)
        return order_count


class ActiveController(rest.RestController):
    """Get active orders
    """
    @wsexpose([models.Order], wtypes.text, int, int, wtypes.text,
              wtypes.text, wtypes.text, bool, bool)
    def get_all(self, type=None, limit=None, offset=None,
                region_id=None, user_id=None, project_id=None,
                owed=None, charged=None):
        conn = pecan.request.db_conn
        orders = conn.get_active_orders(request.context,
                                        type=type,
                                        limit=limit,
                                        offset=offset,
                                        region_id=region_id,
                                        user_id=user_id,
                                        project_id=project_id,
                                        owed=owed,
                                        charged=charged)
        return [models.Order.from_db_model(order)
                for order in orders]


class ResetOrderController(rest.RestController):
    """Reset a bunch of charged orders to uncharged
    """
    @wsexpose(None, body=models.OrderIds)
    def put(self, data):
        conn = pecan.request.db_conn
        try:
            conn.reset_charged_orders(request.context, data.order_ids)
        except Exception:
            LOG.exception("Fail to reset charged orders: %s" % data.order_ids)


class OrdersController(rest.RestController):
    """The controller of resources
    """
    summary = SummaryController()
    resource = ResourceController()
    count = CountController()
    active = ActiveController()
    stopped = StoppedOrderCountController()
    reset = ResetOrderController()

    @pecan.expose()
    def _lookup(self, order_id, *remainder):
        if remainder and not remainder[-1]:
            remainder = remainder[:-1]
        if uuidutils.is_uuid_like(order_id):
            return OrderController(order_id), remainder

    @wsexpose(models.Orders, wtypes.text, wtypes.text,
              datetime.datetime, datetime.datetime, int, int, wtypes.text,
              wtypes.text, wtypes.text, bool)
    def get_all(self, type=None, status=None, start_time=None, end_time=None,
                limit=None, offset=None, region_id=None, project_id=None,
                user_id=None, owed=None):
        """Get queried orders
        If start_time and end_time is not None, will get orders that have bills
        during start_time and end_time, or return all orders directly.
        """
        # bad hack
        if not request.context.is_admin and not project_id:
            return models.Orders.transform(total_count=0,
                                           orders=[])

        conn = pecan.request.db_conn
        orders_db, total_count = conn.get_orders(request.context,
                                                 type=type,
                                                 status=status,
                                                 start_time=start_time,
                                                 end_time=end_time,
                                                 owed=owed,
                                                 limit=limit,
                                                 offset=offset,
                                                 with_count=True,
                                                 region_id=region_id,
                                                 user_id=user_id,
                                                 project_id=project_id)
        orders = []
        for order in orders_db:
            price = self._get_order_price(order,
                                          start_time=start_time,
                                          end_time=end_time)

            order.total_price = gringutils._quantize_decimal(price)

            orders.append(models.Order.from_db_model(order))

        return models.Orders.transform(total_count=total_count,
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

    @wsexpose(None, body=models.OrderPostBody)
    def post(self, data):
        conn = pecan.request.db_conn
        try:
            conn.create_order(request.context, **data.as_dict())
        except Exception as e:
            LOG.exception('Fail to create order: %s, for reason %s' %
                           (data.as_dict(), e))

    @wsexpose(None, body=models.OrderPutBody)
    def put(self, data):
        """Change the unit price of the order"""
        conn = pecan.request.db_conn
        try:
            conn.update_order(request.context, **data.as_dict())
        except Exception as e:
            LOG.exception('Fail to update order: %s, for reason %s' %
                           (data.as_dict(), e))
