# -*- coding: utf-8 -*-

import pecan
import wsme
import datetime
import tablib

from pecan import rest
from pecan import request
from pecan import response

from wsme import types as wtypes

from oslo.config import cfg

from gringotts import exception
from gringotts.api import acl
from gringotts.api.wsmeext_pecan import wsexpose
from gringotts import utils as gringutils
from gringotts.api.v2 import models
from gringotts.db import models as db_models
from gringotts.services import keystone
from gringotts.openstack.common import log
from gringotts.openstack.common import timeutils


OUTPUT_TIME_FORMAT = '%Y-%m-%d %H:%M:%S'
LOG = log.getLogger(__name__)


class ChargesController(rest.RestController):


    @wsexpose(None, wtypes.text, wtypes.text, datetime.datetime,
              datetime.datetime, int, int, status=204)
    def get(self, output_format='xlsx', user_id=None, start_time=None, end_time=None,
            limit=None, offset=None):
        """Export all charges of special user, output formats supported:
           * Excel (Sets + Books)
           * JSON (Sets + Books)
           * YAML (Sets + Books)
           * HTML (Sets)
           * TSV (Sets)
           * CSV (Sets)
        """
        if output_format.lower() not in ["xls", "xlsx", "csv", "json", "yaml"]:
            raise exception.InvalidOutputFormat(output_format=output_format)

        limit_user_id = acl.get_limited_to_user(request.headers, 'uos_staff')

        if limit_user_id:
            user_id = limit_user_id

        headers = (u"UUID", u"充值对象", u"充值对象ID", u"充值金额", u"充值类型", u"充值来源",
                   u"充值人员", u"充值人员ID", u"充值时间", u"状态")
        data = []

        users = {}
        def _get_user(user_id):
            user = users.get(user_id)
            if user:
                return user
            contact = keystone.get_uos_user(user_id)
            user_name = contact['name'] if contact else None
            users[user_id] = models.User(user_id=user_id,
                                         user_name=user_name)
            return users[user_id]

        self.conn = pecan.request.db_conn
        charges = self.conn.get_charges(request.context,
                                        user_id=user_id,
                                        limit=limit,
                                        offset=offset,
                                        start_time=start_time,
                                        end_time=end_time)
        for charge in charges:
            charge.charge_time += datetime.timedelta(hours=8)
            acharge = models.Charge.from_db_model(charge)
            acharge.actor = _get_user(charge.operator)
            acharge.target = _get_user(charge.user_id)
            charge_time = timeutils.strtime(charge.charge_time, fmt=OUTPUT_TIME_FORMAT)

            adata = (acharge.charge_id, acharge.target.user_name, acharge.target.user_id,
                     str(acharge.value), acharge.type, acharge.come_from,
                     acharge.actor.user_id, acharge.actor.user_name,
                     charge_time, u"正常")
            data.append(adata)

        data = tablib.Dataset(*data, headers=headers)

        response.content_type = "application/binary; charset=UTF-8"
        response.content_disposition = "attachment; filename=charges.%s" % output_format
        content = getattr(data, output_format)
        if output_format == 'csv':
            content = content.decode("utf-8").encode("gb2312")
        response.write(content)
        return response


class OrdersController(rest.RestController):
    """Download orders logic
    """
    @wsexpose(None, wtypes.text, wtypes.text, wtypes.text,
              datetime.datetime, datetime.datetime, int, int, wtypes.text,
              wtypes.text, wtypes.text, bool)
    def get_all(self, output_format='xlsx', type=None, status=None, start_time=None, end_time=None,
                limit=None, offset=None, region_id=None, project_id=None, user_id=None, owed=None):
        """Get queried orders
        If start_time and end_time is not None, will get orders that have bills
        during start_time and end_time, or return all orders directly.
        """
        limit_user_id = acl.get_limited_to_user(request.headers, 'uos_staff')

        if limit_user_id: # normal user
            user_id = None
            projects = keystone.get_projects_by_user(limit_user_id)
            _project_ids = [project['id'] for project in projects]
            if project_id:
                project_ids = [project_id] if project_id in _project_ids else _project_ids
            else:
                project_ids = _project_ids
        else: # accountant
            if project_id: # look up specified project
                project_ids = [project_id]
            else: # look up all projects
                project_ids = None

        users = {}
        projects = {}

        def _get_user(user_id):
            user = users.get(user_id)
            if user:
                return user
            contact = keystone.get_uos_user(user_id)
            user_name = contact['name'] if contact else None
            users[user_id] = models.User(user_id=user_id,
                                         user_name=user_name)
            return users[user_id]

        def _get_project(project_id):
            project = projects.get(project_id)
            if project:
                return project
            project = keystone.get_project(project_id)
            project_name = project.name if project else None
            projects[project_id] = models.SimpleProject(project_id=project_id,
                                                        project_name=project_name)
            return projects[project_id]

        headers = (u"资源ID", u"资源名称", u"资源类型", u"资源状态", u"单价", u"金额", u"区域",
                   u"用户ID", u"用户名称", u"项目ID", u"项目名称", u"创建时间")
        data = []

        adata = (u"过滤条件: 资源类型: %s, 资源状态: %s，用户ID: %s, 项目ID: %s, 区域: %s, 起始时间: %s,  结束时间: %s" %
                 (type, status, user_id, project_id, region_id, start_time, end_time),
                 "", "", "", "", "", "", "", "", "", "", "")
        data.append(adata)

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
                                                 project_ids=project_ids)
        orders = []
        for order in orders_db:
            price = self._get_order_price(order,
                                          start_time=start_time,
                                          end_time=end_time)
            user = _get_user(order.user_id)
            project = _get_project(order.project_id)
            order.created_at += datetime.timedelta(hours=8)
            created_at = timeutils.strtime(order.created_at, fmt=OUTPUT_TIME_FORMAT)
            adata = (order.resource_id, order.resource_name, order.type, order.status,
                     order.unit_price, order.total_price, order.region_id,
                     user.user_id, user.user_name,
                     project.project_id, project.project_name,
                     created_at)
            data.append(adata)

        data = tablib.Dataset(*data, headers=headers)

        response.content_type = "application/binary; charset=UTF-8"
        response.content_disposition = "attachment; filename=orders.%s" % output_format
        content = getattr(data, output_format)
        if output_format == 'csv':
            content = content.decode("utf-8").encode("gb2312")
        response.write(content)
        return response

    def _get_order_price(self, order, start_time=None, end_time=None):
        if not all([start_time, end_time]):
            return order.total_price

        conn = pecan.request.db_conn
        total_price = conn.get_bills_sum(request.context,
                                         start_time=start_time,
                                         end_time=end_time,
                                         order_id=order.order_id)
        return total_price


class DownloadsController(rest.RestController):
    """Manages operations on the downloads operations
    """
    charges = ChargesController()
    orders = OrdersController()
