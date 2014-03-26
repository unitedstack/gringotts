import calendar
import pecan
import wsme
import datetime
import decimal

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
from gringotts.openstack.common import memorycache
from gringotts.openstack.common import timeutils
from gringotts.openstack.common import uuidutils


LOG = log.getLogger(__name__)


class SubsController(rest.RestController):
    """The controller of resources
    """

    @wsexpose(models.Bills, datetime.datetime, datetime.datetime,
              wtypes.text, int, int)
    def get_all(self, start_time=None, end_time=None, type=None,
                limit=None, offset=None):
        """Get all bills, filter by type, start time, and end time
        """
        conn = pecan.request.db_conn

        bills_db = list(conn.get_bills(request.context,
                                       start_time=start_time,
                                       end_time=end_time,
                                       type=type,
                                       limit=limit,
                                       offset=offset))
        total_count, total_price = conn.get_bills_count_and_sum(
            request.context,
            start_time=start_time,
            end_time=end_time,
            type=type)

        total_price=gringutils._quantize_decimal(total_price)

        bills = []
        for bill in bills_db:
            bills.append(models.Bill.from_db_model(bill))

        return models.Bills.transform(total_price=total_price,
                                      total_count=total_count,
                                      bills=bills)

    @wsexpose(models.Subscription, body=models.SubscriptionPostBody)
    def post(self, data):
        conn = pecan.request.db_conn
        subscription = conn.create_subscription(request.context,
                                                **data.as_dict())
        return subscription

    @wsexpose(models.Subscription, body=models.SubscriptionPutBody)
    def put(self, data):
        conn = pecan.request.db_conn
        subscription = conn.update_subscription(request.context,
                                                **data.as_dict())
        return subscription
