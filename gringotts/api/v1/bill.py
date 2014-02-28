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
from gringotts import utils as gringutils

from gringotts.api.v1 import models
from gringotts.db import models as db_models
from gringotts.openstack.common import log
from gringotts.openstack.common import timeutils
from gringotts.openstack.common import uuidutils


LOG = log.getLogger(__name__)


class TrendsController(rest.RestController):
    """Summary every order type's consumption
    """
    @wsexpose([models.Trend])
    def get(self):
        """Get summary of all kinds of orders in the last year
        """
        conn = pecan.request.db_conn

        # The last 12 months from now.
        # NOTE(suo): Adding another hour to each end_month is to
        # include the cross month bill.
        now = datetime.datetime.utcnow()
        first_day = datetime.datetime(now.year, now.month, 1)
        now_day = datetime.datetime(now.year, now.month, now.day) + \
                datetime.timedelta(hours=25)

        months = [(first_day, now_day)]

        for i in range(11):
            start_month = first_day - relativedelta(months=i+1)
            month_day = calendar.monthrange(start_month.year, start_month.month)[1]
            end_month = start_month + datetime.timedelta(days=month_day-1) + \
                datetime.timedelta(hours=25)
            months.append((start_month, end_month))

        trends = []

        for start_time, end_time in months:
            bills_sum = conn.get_bills_sum(request.context,
                                           start_time=start_time,
                                           end_time=end_time)

            bills_sum = gringutils._quantize_decimal(bills_sum)

            trends.append(models.Trend.transform(
                start_time=start_time.date(),
                end_time=(end_time-datetime.timedelta(hours=25)).date(),
                consumption=bills_sum))
        return trends


class BillsController(rest.RestController):
    """The controller of resources
    """
    trends = TrendsController()

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
