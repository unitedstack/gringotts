import datetime

from oslo.config import cfg
import pecan
from pecan import request
from pecan import rest
from wsme import types as wtypes
from wsmeext.pecan import wsexpose

from gringotts.api import acl
from gringotts.api.v2 import models
from gringotts import constants as const
from gringotts import exception
from gringotts import master
from gringotts.openstack.common import log
from gringotts.openstack.common import uuidutils
from gringotts.openstack.common import timeutils
from gringotts.services import keystone
from gringotts import utils as gringutils

LOG = log.getLogger(__name__)


class OrderController(rest.RestController):
    """For one single order, getting its detail consumptions."""

    _custom_actions = {
        'order': ['GET'],
        'close': ['PUT'],
        'activate_auto_renew': ['PUT'],
        'switch_auto_renew': ['PUT'],
        'renew': ['PUT'],
    }

    def __init__(self, order_id):
        self._id = order_id
        self.master_api = master.API()

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
        except Exception:
            LOG.error('Order(%s)\'s bills not found' % self._id)
            raise exception.OrderBillsNotFound(order_id=self._id)
        return bills

    @wsexpose(models.Bills, datetime.datetime, datetime.datetime, int, int)
    def get(self, start_time=None, end_time=None, limit=None, offset=None):
        """Get this order's detail."""

        if limit and limit < 0:
            raise exception.InvalidParameterValue(err="Invalid limit")
        if offset and offset < 0:
            raise exception.InvalidParameterValue(err="Invalid offset")

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

    @wsexpose(models.Order)
    def order(self):
        conn = pecan.request.db_conn
        order = conn.get_order(request.context, self._id)
        return models.Order.from_db_model(order)

    @wsexpose(models.Order)
    def close(self):
        """Close this order

        Close means set order's status to deleted in database, then stop
        the cron job in apscheduler.
        """
        conn = pecan.request.db_conn
        try:
            order = conn.close_order(request.context, self._id)
        except Exception:
            msg = "Fail to close the order %s" % self._id
            LOG.exception(msg)
            raise exception.DBError(reason=msg)
        self.master_api.delete_sched_jobs(request.context, self._id)
        return models.Order.from_db_model(order)

    def _validate_renew(self, renew):
        err = None
        if 'method' not in renew or 'period' not in renew:
            err = 'Must specify method and period'
        elif renew['method'] not in ['month', 'year']:
            err = 'Wrong method, should be month or year'
        elif not isinstance(renew['period'], int) or renew['period'] <= 0:
            err = 'Wrong period, should be an integer greater than 0'

        if err:
            LOG.warn(err)
            raise exception.InvalidParameterValue(err=err)

    @wsexpose(models.Order, body=models.Renew)
    def activate_auto_renew(self, data):
        """Activate auto renew of this order
        """
        self._validate_renew(data.as_dict())
        conn = pecan.request.db_conn
        try:
            order = conn.activate_auto_renew(request.context, self._id, data)
        except exception.OrderNotFound as e:
            LOG.warn(e)
            raise
        except exception.OrderRenewError as e:
            LOG.warn(e)
            raise
        except Exception:
            msg = "Fail to activate auto renew of the order %s" % self._id
            LOG.exception(msg)
            raise exception.DBError(reason=msg)
        return models.Order.from_db_model(order)

    @wsexpose(models.Order, body=models.SwitchRenew)
    def switch_auto_renew(self, data):
        """Start/Stop auto renew of this order
        """
        if data.action not in ['start', 'stop']:
            err = "Wrong switch renew action, should be start or stop"
            LOG.warn(err)
            raise exception.InvalidParameterValue(err=err)

        conn = pecan.request.db_conn
        try:
            order = conn.switch_auto_renew(request.context, self._id,
                                           data.action)
        except exception.OrderNotFound as e:
            LOG.warn(e)
            raise
        except exception.OrderRenewError as e:
            LOG.warn(e)
            raise
        except Exception:
            msg = "Fail to switch auto renew of the order %s" % self._id
            LOG.exception(msg)
            raise exception.DBError(reason=msg)
        return models.Order.from_db_model(order)

    @wsexpose(models.Order, body=models.Renew)
    def renew(self, data):
        """renew the order manually

        1. Caculate price needed to deduct
        2. Change cron_time and deduct account in the same session
        3. Change cron job in master
        """
        self._validate_renew(data.as_dict())
        conn = pecan.request.db_conn
        try:
            order = conn.renew_order(request.context, self._id, data)
            self.master_api.change_monthly_job_time(
                request.context, self._id,
                timeutils.isotime(order.cron_time),
                clear_date_jobs=True)
        except exception.OrderNotFound as e:
            LOG.warn(e)
            raise
        except exception.OrderRenewError as e:
            LOG.warn(e)
            raise
        except Exception:
            msg = "Fail to renew the order %s" % self._id
            LOG.exception(msg)
            raise exception.DBError(reason=msg)
        return models.Order.from_db_model(order)


class SummaryController(rest.RestController):
    """Summary every order type's consumption."""

    @wsexpose(models.Summaries,
              datetime.datetime, datetime.datetime, wtypes.text,
              wtypes.text, wtypes.text, wtypes.text)
    def get(self, start_time=None, end_time=None, region_id=None,
            user_id=None, project_id=None, read_deleted=None):
        """Get summary of all kinds of orders."""
        limit_user_id = acl.get_limited_to_user(
            request.headers, 'uos_support_staff')

        if limit_user_id:  # normal user
            user_id = None
            projects = keystone.get_projects_by_user(limit_user_id)
            _project_ids = [project['id'] for project in projects]
            if project_id:
                project_ids = ([project_id]
                               if project_id in _project_ids
                               else _project_ids)
            else:
                project_ids = _project_ids
        else:  # accountant
            if project_id:  # look up specified project
                project_ids = [project_id]
            else:  # look up all projects
                project_ids = []

        if project_ids:
            project_ids = list(set(project_ids) - set(cfg.CONF.ignore_tenants))

        # good way to go
        conn = pecan.request.db_conn

        if read_deleted:
            if read_deleted.lower() == 'true':
                read_deleted = True
            elif read_deleted.lower() == 'false':
                read_deleted = False
            else:
                read_deleted = True
        else:
            read_deleted = True

        # Get all orders of this particular context at one time
        orders_db = list(conn.get_orders(request.context,
                                         start_time=start_time,
                                         end_time=end_time,
                                         user_id=user_id,
                                         project_ids=project_ids,
                                         region_id=region_id,
                                         read_deleted=read_deleted))

        total_price = gringutils._quantize_decimal(0)
        total_count = 0
        summaries = []

        # loop all order types
        for order_type in const.ORDER_TYPE:

            order_total_price = gringutils._quantize_decimal(0)
            order_total_count = 0

            # One user's order records will not be very large, so we can
            # traverse them directly
            for order in orders_db:
                if order.type != order_type:
                    if (order.type == const.RESOURCE_FLOATINGIPSET
                            and order_type == const.RESOURCE_FLOATINGIP):
                        # floatingipset consumption belongs to floatingip
                        pass
                    else:
                        continue
                price, count = self._get_order_price_and_count(
                    order, start_time=start_time, end_time=end_time)
                order_total_price += price
                order_total_count += count

            summaries.append(models.Summary.transform(
                total_count=order_total_count,
                order_type=order_type,
                total_price=order_total_price)
            )
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
    """Order related to resource."""

    @wsexpose(models.Order, wtypes.text)
    def get(self, resource_id):
        conn = pecan.request.db_conn
        order = conn.get_order_by_resource_id(request.context,
                                              resource_id)
        return models.Order.from_db_model(order)


class CountController(rest.RestController):
    """Get number of active order."""

    @wsexpose(int, wtypes.text, bool, wtypes.text)
    def get(self, region_id, owed=None, type=None):
        conn = pecan.request.db_conn
        order_count = conn.get_active_order_count(request.context,
                                                  region_id=region_id,
                                                  owed=owed,
                                                  type=type)
        return order_count


class StoppedOrderCountController(rest.RestController):
    """Get number of active order."""

    @wsexpose(int, wtypes.text, bool, wtypes.text)
    def get(self, region_id, owed=None, type=None):
        conn = pecan.request.db_conn
        order_count = conn.get_stopped_order_count(request.context,
                                                   region_id=region_id,
                                                   owed=owed,
                                                   type=type)
        return order_count


class ActiveController(rest.RestController):
    """Get active orders."""

    @wsexpose([models.Order], wtypes.text, int, int, wtypes.text,
              wtypes.text, wtypes.text, bool, bool)
    def get_all(self, type=None, limit=None, offset=None,
                region_id=None, user_id=None, project_id=None,
                owed=None, charged=None):

        if limit and limit < 0:
            raise exception.InvalidParameterValue(err="Invalid limit")
        if offset and offset < 0:
            raise exception.InvalidParameterValue(err="Invalid offset")

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
    """Reset a bunch of charged orders to uncharged."""

    @wsexpose(None, body=models.OrderIds)
    def put(self, data):
        conn = pecan.request.db_conn
        try:
            conn.reset_charged_orders(request.context, data.order_ids)
        except Exception:
            LOG.exception("Fail to reset charged orders: %s" % data.order_ids)


class OrdersController(rest.RestController):
    """The controller of resources."""

    summary = SummaryController()
    resource = ResourceController()
    count = CountController()
    active = ActiveController()
    stopped = StoppedOrderCountController()
    reset = ResetOrderController()

    def __init__(self):
        self.master_api = master.API()

    @pecan.expose()
    def _lookup(self, order_id, *remainder):
        if remainder and not remainder[-1]:
            remainder = remainder[:-1]
        if uuidutils.is_uuid_like(order_id):
            return OrderController(order_id), remainder

    @wsexpose(models.Orders, wtypes.text, wtypes.text,
              datetime.datetime, datetime.datetime, int, int, wtypes.text,
              wtypes.text, wtypes.text, wtypes.text, bool, [wtypes.text])
    def get_all(self, type=None, status=None, start_time=None, end_time=None,
                limit=None, offset=None, resource_id=None, region_id=None,
                project_id=None, user_id=None, owed=None, bill_methods=None):
        """Get queried orders
        If start_time and end_time is not None, will get orders that have bills
        during start_time and end_time, or return all orders directly.
        """

        if limit and limit < 0:
            raise exception.InvalidParameterValue(err="Invalid limit")
        if offset and offset < 0:
            raise exception.InvalidParameterValue(err="Invalid offset")

        limit_user_id = acl.get_limited_to_user(
            request.headers, 'uos_support_staff')

        if limit_user_id:  # normal user
            user_id = None
            projects = keystone.get_projects_by_user(limit_user_id)
            _project_ids = [project['id'] for project in projects]
            if project_id:
                project_ids = ([project_id]
                               if project_id in _project_ids
                               else _project_ids)
            else:
                project_ids = _project_ids
        else:  # accountant
            if project_id:  # look up specified project
                project_ids = [project_id]
            else:  # look up all projects
                project_ids = None

        if project_ids:
            project_ids = list(set(project_ids) - set(cfg.CONF.ignore_tenants))

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
                                                 resource_id=resource_id,
                                                 bill_methods=bill_methods,
                                                 region_id=region_id,
                                                 user_id=user_id,
                                                 project_ids=project_ids)
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
            order = conn.create_order(request.context, **data.as_dict())
            self.master_api.create_monthly_job(
                request.context, order.order_id,
                timeutils.isotime(order.cron_time))
        except Exception as e:
            LOG.exception('Fail to create order: %s, for reason %s' %
                          (data.as_dict(), e))

    @wsexpose(None, body=models.OrderPutBody)
    def put(self, data):
        """Change the unit price of the order."""
        conn = pecan.request.db_conn
        try:
            conn.update_order(request.context, **data.as_dict())
        except Exception as e:
            LOG.exception('Fail to update order: %s, for reason %s' %
                          (data.as_dict(), e))
