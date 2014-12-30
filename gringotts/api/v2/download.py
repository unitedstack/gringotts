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

        user_id, __ = acl.get_limited_to_accountant(request.headers)

        if not user_id:
            user_id = user_id

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
            acharge = models.Charge.from_db_model(charge)
            acharge.actor = _get_user(charge.operator)
            acharge.target = _get_user(charge.user_id)

            adata = (acharge.charge_id, acharge.target.user_name, acharge.target.user_id,
                     str(acharge.value), acharge.type, acharge.come_from,
                     acharge.actor.user_id, acharge.actor.user_name,
                     acharge.charge_time, u"正常")
            data.append(adata)

        data = tablib.Dataset(*data, headers=headers)

        response.content_type = "application/binary; charset=UTF-8"
        response.content_disposition = "attachment; filename=charges.%s" % output_format
        content = getattr(data, output_format)
        if output_format == 'csv':
            content = content.decode("utf-8").encode("gb2312")
        response.write(content)
        return response


class DownloadsController(rest.RestController):
    """Manages operations on the downloads operations
    """
    charges = ChargesController()
