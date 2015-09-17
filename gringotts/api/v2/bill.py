import calendar
import datetime

from oslo.config import cfg
import pecan
from pecan import rest
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from gringotts.api import acl
from gringotts.api import app
from gringotts.api.v2 import models
from gringotts import exception
from gringotts.openstack.common import log
from gringotts.openstack.common import memorycache
from gringotts.openstack.common import timeutils
from gringotts.openstack.common import uuidutils
from gringotts import utils as gringutils


LOG = log.getLogger(__name__)

# NOTE(suo): The bill sum in the past won't be changed forever, so
#            we can cache them a little longer.
BILL_CACHE_SECONDS = 60 * 60 * 24 * 30
MC = None


def _get_cache():
    global MC
    if MC is None:
        MC = memorycache.get_client()
    return MC


def reset_cache():
    """Reset the cache

    Mainly for testing purposes and update
    availability_zone for host aggregate
    """
    global MC
    MC = None


def _make_cache_key(region_id, user_id, project_id, start_time, end_time):
    start_time = timeutils.isotime(start_time)
    end_time = timeutils.isotime(end_time)
    if project_id:
        key = "%s-%s-%s-%s" % (project_id, region_id, start_time, end_time)
    elif user_id:
        key = "%s-%s-%s-%s" % (user_id, region_id, start_time, end_time)
    # NOTE(suo): As python-memcached only accepts byte string as memcache key,
    # not unicode, so this key should be encoded using str()
    return str(key)


class TrendsController(rest.RestController):
    """Summary every order type's consumption
    """
    @wsme_pecan.wsexpose([models.Trend], datetime.datetime,
                         wtypes.text, wtypes.text,
                         wtypes.text, wtypes.text)
    def get(self, today=None, type=None, user_id=None,
            project_id=None, region_id=None):
        """Get summary of all kinds of orders in the latest 12 month or 12 day

        :param today: Client's today wee hour
        :param type: month, day
        """
        limit_user_id = acl.get_limited_to_user(pecan.request.headers,
                                                'uos_staff')
        if limit_user_id:
            user_id = limit_user_id
        # accountant can look up any user, if not sepcify, look up itself
        elif not user_id:
            user_id = pecan.request.context.user_id

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
            latest_end = latest_start + datetime.timedelta(
                days=next_month_days)
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
                start_day = today - datetime.timedelta(days=i + 1)
                end_day = start_day + datetime.timedelta(days=1)
                periods.append((start_day, end_day))
            LOG.debug('Latest 12 days: %s' % periods)

        # NOTE(suo): The latest period will not read cache
        for i in range(12):
            read_cache = True
            if i == 0:
                read_cache = False
            bills_sum = self._get_bills_sum(pecan.request.context,
                                            conn,
                                            user_id=user_id,
                                            project_id=project_id,
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

    def _get_bills_sum(self, context, conn, user_id, project_id, region_id,
                       start_time, end_time, read_cache=True):
        if read_cache:
            cache = _get_cache()
            key = _make_cache_key(region_id, context.user_id, project_id,
                                  start_time, end_time)

            bills_sum = cache.get(key)
            if not bills_sum and bills_sum != 0:
                bills_sum = conn.get_bills_sum(context,
                                               user_id=user_id,
                                               project_id=project_id,
                                               region_id=region_id,
                                               start_time=start_time,
                                               end_time=end_time)
                cache.set(key, bills_sum, BILL_CACHE_SECONDS)
        else:
            bills_sum = conn.get_bills_sum(context,
                                           user_id=user_id,
                                           project_id=project_id,
                                           region_id=region_id,
                                           start_time=start_time,
                                           end_time=end_time)
        return bills_sum


class DetailController(rest.RestController):
    """Get the detail of bills."""
    @wsme_pecan.wsexpose(models.Bills, datetime.datetime, datetime.datetime,
                         wtypes.text, wtypes.text, int, int)
    def get_all(self, start_time=None, end_time=None, type=None,
                project_id=None, limit=None, offset=None):

        if limit and limit < 0:
            raise exception.InvalidParameterValue(err="Invalid limit")
        if offset and offset < 0:
            raise exception.InvalidParameterValue(err="Invalid offset")

        conn = pecan.request.db_conn

        bills_db = list(conn.get_bills(pecan.request.context,
                                       project_id=project_id,
                                       start_time=start_time,
                                       end_time=end_time,
                                       type=type,
                                       limit=limit,
                                       offset=offset))
        total_count, total_price = conn.get_bills_count_and_sum(
            pecan.request.context,
            project_id=project_id,
            start_time=start_time,
            end_time=end_time,
            type=type)

        total_price = gringutils._quantize_decimal(total_price)

        bills = []
        for bill in bills_db:
            bills.append(models.Bill.from_db_model(bill))

        return models.Bills.transform(total_price=total_price,
                                      total_count=total_count,
                                      bills=bills)


class CloseController(rest.RestController):

    def __init__(self):
        self.external_client = app.external_client()

    @wsme_pecan.wsexpose(models.BillResult, body=models.BillBody)
    def put(self, data):
        """Close a bill

        Four steps to close a bill:
        1. get user_id via order_id
        2. get external account balance via user_id
        3. close the bill
        4. deduct external account

        If one of (1, 2, 3) step fails, just raise exception to stop the
        procedure, it will create this bill in next regular deducting circle.

        But if the 4th step fails, we should save the deducting record in our
        system to sync with the external system when it works again.
        """

        conn = pecan.request.db_conn
        external_balance = None
        ctxt = pecan.request.context

        try:
            if cfg.CONF.external_billing.enable:
                # 1. get user_id via order_id
                user_id = conn.get_order(ctxt, data.order_id).user_id

                # 2. get external account balance via user_id
                external_balance = self.external_client.get_external_balance(
                    user_id)['data'][0]['money']

            # 3. close the bill
            result = conn.close_bill(pecan.request.context,
                                     data['order_id'],
                                     action_time=data['action_time'],
                                     external_balance=external_balance)

            if cfg.CONF.external_billing.enable and result['type'] >= 0:
                # 4. deduct external account
                req_id = uuidutils.generate_uuid()
                extdata = dict(resource_id=result['resource_id'],
                               resource_name=result['resource_name'],
                               resource_type=result['resource_type'],
                               region_id=result['region_id'],
                               order_id=data.order_id)
                try:
                    self.external_client.deduct_external_account(
                        user_id,
                        str(result['deduct_value']),
                        type="1",
                        remark="come from ustack",
                        req_id=req_id,
                        **extdata)
                except Exception as e:
                    LOG.exception("Fail to deduct external account, "
                                  "as reason: %s", e)
                    conn.deduct_account(ctxt, user_id, deduct=False,
                                        money=result['deduct_value'],
                                        reqId=req_id,
                                        type="1",
                                        remark="close bill backup",
                                        extData=extdata)
            LOG.debug('Close bill for order %s successfully.',
                      data['order_id'])
            return models.BillResult(**result)
        except Exception:
            LOG.exception('Fail to close bill for the order: %s',
                          data['order_id'])
            raise exception.BillCloseFailed(order_id=data['order_id'])


class UpdateController(rest.RestController):

    def __init__(self):
        self.external_client = app.external_client()

    @wsme_pecan.wsexpose(models.BillResult, body=models.BillBody)
    def put(self, data):
        """Update a bill

        Four steps to update a bill:
        1. get user_id via order_id
        2. get external account balance via user_id
        3. update the bill
        4. deduct external account

        If one of (1, 2, 3) step fails, just raise exception to stop
        the procedure, it will create this bill in next regular deducting
        circle.

        But if the 4th step fails, we should save the deducting record in our
        system to sync with the external system when it works again.
        """
        conn = pecan.request.db_conn
        external_balance = None
        ctxt = pecan.request.context

        try:
            if cfg.CONF.external_billing.enable:
                # 1. get user_id via order_id
                user_id = conn.get_order(ctxt, data.order_id).user_id

                # 2. get external account balance via user_id
                external_balance = self.external_client.get_external_balance(
                    user_id)['data'][0]['money']

            # 3. update the bill
            result = conn.update_bill(ctxt, data['order_id'],
                                      external_balance=external_balance)

            if cfg.CONF.external_billing.enable and result['type'] >= 0:
                # 4. deduct external account
                req_id = uuidutils.generate_uuid()
                extdata = dict(resource_id=result['resource_id'],
                               resource_name=result['resource_name'],
                               resource_type=result['resource_type'],
                               region_id=result['region_id'],
                               order_id=data.order_id)
                try:
                    self.external_client.deduct_external_account(
                        user_id,
                        str(result['deduct_value']),
                        type="1",
                        remark="come from ustack",
                        req_id=req_id,
                        **extdata)
                except Exception as e:
                    LOG.exception("Fail to deduct external account, "
                                  "as reason: %s", e)
                    conn.deduct_account(ctxt, user_id, deduct=False,
                                        money=result['deduct_value'],
                                        reqId=req_id,
                                        type="1",
                                        remark="update bill backup",
                                        extData=extdata)
            LOG.debug('Update bill for order %s successfully.',
                      data['order_id'])
            return models.BillResult(**result)
        except Exception:
            LOG.exception('Fail to update bill for the order: %s',
                          data['order_id'])
            raise exception.BillUpdateFailed(order_id=data['order_id'])


class BillsController(rest.RestController):
    """The controller of resources
    """
    trends = TrendsController()
    detail = DetailController()
    update = UpdateController()
    close = CloseController()

    def __init__(self):
        self.external_client = app.external_client()

    @wsme_pecan.wsexpose(models.Bills, datetime.datetime, datetime.datetime,
                         wtypes.text, wtypes.text)
    def get_all(self, start_time=None, end_time=None, type=None,
                project_id=None):
        """Get all bills, filter by type, start time, and end time."""
        conn = pecan.request.db_conn
        total_price = conn.get_bills_sum(pecan.request.context,
                                         project_id=project_id,
                                         start_time=start_time,
                                         end_time=end_time,
                                         type=type)
        return models.Bills.transform(
            total_price=gringutils._quantize_decimal(total_price))

    @wsme_pecan.wsexpose(models.BillResult, body=models.BillBody)
    def post(self, data):
        """Create a bill

        Four steps to create a bill:
        1. get user_id via order_id
        2. get external account balance via user_id
        3. create a bill
        4. deduct external account

        If one of (1, 2, 3) step fails, just raise exception to stop the
        procedure, it will create this bill in next regular deducting circle.

        But if the 4th step fails, we should save the deducting record in our
        system to sync with the external system when it works again.
        """
        conn = pecan.request.db_conn
        external_balance = None
        ctxt = pecan.request.context

        try:
            if cfg.CONF.external_billing.enable:
                # 1. get user_id via order_id
                user_id = conn.get_order(ctxt, data.order_id).user_id

                # 2. get external account balance via user_id
                external_balance = self.external_client.get_external_balance(
                    user_id)['data'][0]['money']

            # 3. create bill
            result = conn.create_bill(ctxt, data['order_id'],
                                      action_time=data['action_time'],
                                      remarks=data['remarks'],
                                      end_time=data['end_time'],
                                      external_balance=external_balance)

            if cfg.CONF.external_billing.enable and result['type'] >= 0:
                # 4. deduct external account
                req_id = uuidutils.generate_uuid()
                extdata = dict(resource_id=result['resource_id'],
                               resource_name=result['resource_name'],
                               resource_type=result['resource_type'],
                               region_id=result['region_id'],
                               order_id=data.order_id)
                try:
                    self.external_client.deduct_external_account(
                        user_id,
                        str(result['deduct_value']),
                        type="1",
                        remark="come from ustack",
                        req_id=req_id,
                        **extdata)
                except Exception as e:
                    LOG.exception("Fail to deduct external account, "
                                  "as reason: %s", e)
                    conn.deduct_account(ctxt, user_id, deduct=False,
                                        money=result['deduct_value'],
                                        reqId=req_id,
                                        type="1",
                                        remark="create bill backup",
                                        extData=extdata)
            LOG.debug('Create bill for order %s successfully.',
                      data['order_id'])
            return models.BillResult(**result)
        except Exception:
            LOG.exception('Fail to create bill for the order: %s',
                          data['order_id'])
            raise exception.BillCreateFailed(order_id=data['order_id'])
