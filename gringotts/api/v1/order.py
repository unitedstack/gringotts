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


class OrdersController(rest.RestController):
    """The controller of resources
    """
    @pecan.expose()
    def _lookup(self, order_id, *remainder):
        if remainder and not remainder[-1]:
            remainder = remainder[:-1]
        return OrderController(order_id), remainder

    @wsexpose(models.Orders, wtypes.text, wtypes.text, wtypes.text)
    def get_all(self, start_time=None, end_time=None, type=None):
        """Get all orders, filter by start_time, end_time, type
        """
        conn = pecan.request.db_conn

        orders_db = conn.get_orders(request.context,
                                    start_time=start_time,
                                    end_time=end_time,
                                    type=type)

        orders = []
        total_price = 0
        order_amount = len(orders)

        for order in orders_db:
            total_price += order.total_price
            orders.append(models.Order.from_db_model(order)

        return models.Orders(total_price=total_price,
                             order_amount=order_amount,
                             orders=orders)
