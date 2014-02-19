#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# filename   : hooks.py
# created at : 2013-07-01 21:05:45

from oslo.config import cfg
from pecan import hooks

from gringotts.context import RequestContext
from gringotts.api import acl


class ConfigHook(hooks.PecanHook):
    """Attach the configuration object to the request
    so controllers can get it.
    """

    def before(self, state):
        state.request.cfg = cfg.CONF


class DBHook(hooks.PecanHook):
    """Attache the db connection to the request
    """

    def __init__(self, conn):
        self.conn = conn

    def before(self, state):
        state.request.db_conn = self.conn


class ContextHook(hooks.PecanHook):
    """Configures a request context and attaches it to the request.
    """

    def before(self, state):
        user_id = state.request.headers.get('X-User-Id')
        project_id = state.request.headers.get('X-Project-Id')
        auth_token = state.request.headers.get('X-Auth-Token')
        is_admin = acl.context_is_admin(state.request.headers)
        is_staff = False

        state.request.context = RequestContext(
            auth_token=auth_token,
            user_id=user_id,
            project_id=project_id,
            is_admin=is_admin,
            is_staff=is_staff)
