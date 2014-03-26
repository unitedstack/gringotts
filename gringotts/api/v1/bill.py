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

# NOTE(suo): The bill sum in the past will not change forever, so
#            we can cache them a little longer.
BILL_CACHE_SECONDS = 60 * 60 * 24
MC = None


def _get_cache():
    global MC
    if MC is None:
        MC = memorycache.get_client()
    return MC


def reset_cache():
    """Reset the cache, mainly for testing purposes and update
    availability_zone for host aggregate
    """
    global MC
    MC = None


def _make_cache_key(region_id, project_id, start_time, end_time):
    if region_id:
        return "%s-%s-%s-%s" % (project_id, region_id, start_time, end_time)
    else:
        return "%s-%s-%s" % (project_id, start_time, end_time)


class TrendsController(rest.RestController):
    """Summary every order type's consumption
    """
    @wsexpose([models.Trend], datetime.datetime, wtypes.text, wtypes.text)
    def get(self, today=None, type=None, region_id=None):
        """Get summary of all kinds of orders in the latest 12 month or 12 day

        :param today: Client's today wee hour
        :param type: month, day
        """
        conn = pecan.request.db_conn
        trends = []
        periods = []

        if not type:
            type = 'month'
        if not today:
            now = datetime.datetime.utcnow()
            today = datetime.datetime(now.year, now.month, now.day)

        # The latest 12 months
        if type == 'month':
            if calendar.monthrange(today.year, today.month)[1] == today.day:
                latest_start = today
            else:
                latest_start = today - datetime.timedelta(days=today.day)
            next_month_days = gringutils.next_month_days(latest_start.year,
                                                         latest_start.month)
            latest_end = latest_start + datetime.timedelta(days=next_month_days)
            periods = [(latest_start, latest_end)]

            for i in range(11):
                last = periods[-1][0]
                last_days = calendar.monthrange(last.year, last.month)[1]
                start_month = last - datetime.timedelta(days=last_days)
                periods.append((start_month, last))
            LOG.debug('Latest 12 months: %s' % periods)
        # The latest 12 days
        elif type == 'day':
            latest_end = today + datetime.timedelta(days=1)
            periods = [(today, latest_end)]

            for i in range(11):
                start_day = today - datetime.timedelta(days=i+1)
                end_day = start_day + datetime.timedelta(days=1)
                periods.append((start_day, end_day))
            LOG.debug('Latest 12 days: %s' % periods)

        # NOTE(suo): The latest period will not read cache
        for i in range(12):
            read_cache = True
            if i == 0:
                read_cache = False
            bills_sum = self._get_bills_sum(request.context,
                                            conn,
                                            region_id=region_id,
                                            start_time=periods[i][0],
                                            end_time=periods[i][1],
                                            read_cache=read_cache)
            bills_sum = gringutils._quantize_decimal(bills_sum)

            trends.insert(0, models.Trend.transform(
                start_time=periods[i][0],
                end_time=periods[i][-1],
                consumption=bills_sum))

        return trends

    def _get_bills_sum(self, context, conn, region_id, start_time, end_time,
                       read_cache=True):
        if read_cache:
            cache = _get_cache()
            key = _make_cache_key(context.project_id, region_id,
                                  start_time, end_time)

            bills_sum = cache.get(key)
            if not bills_sum and bills_sum != 0:
                bills_sum = conn.get_bills_sum(context,
                                               region_id=region_id,
                                               start_time=start_time,
                                               end_time=end_time)
                cache.set(key, bills_sum, BILL_CACHE_SECONDS)
        else:
            bills_sum = conn.get_bills_sum(context,
                                           region_id=region_id,
                                           start_time=start_time,
                                           end_time=end_time)
        return bills_sum


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

    @wsexpose(None, body=models.BillBody)
    def post(self, data):
        conn = pecan.request.db_conn
        try:
            conn.create_bill(request.context, data['order_id'],
                             action_time=data['action_time'],
                             remarks=data['remarks'])
            LOG.debug('Create bill for order %s successfully.' % data['order_id'])
        except Exception:
            LOG.exception('Fail to create bill for the order: %s' % data['order_id'])
            raise exception.BillCreateFailed(order_id=data['order_id'])

    @wsexpose(None, body=models.BillBody)
    def put(self, data):
        conn = pecan.request.db_conn
        try:
            conn.close_bill(request.context, data['order_id'],
                            action_time=data['action_time'])
            LOG.debug('Close bill for order %s successfully.' % data['order_id'])
        except Exception:
            LOG.exception('Fail to close bill for the order: %s' % data['order_id'])
            raise exception.BillCloseFailed(order_id=data['order_id'])
