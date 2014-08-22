import pecan
import wsme

from pecan import rest
from pecan import request
from wsmeext.pecan import wsexpose


class FixController(rest.RestController):
    """For one single order, getting its detail consumptions
    """
    @wsexpose(None)
    def get(self):
        """Return this order's detail
        """
        conn = pecan.request.db_conn
        orders = conn.get_orders(request.context, status='stopped')
        for order in orders:
            conn.fix_stopped_order(request.context, order.order_id)
