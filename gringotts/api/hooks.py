#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# filename   : hooks.py
# created at : 2013-07-01 21:05:45

from oslo.config import cfg
from pecan import hooks

from gringotts.context import RequestContext


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

    The following HTTP request headers are used:

    X-User-Id or X-User:
        Used for context.user_id.

    X-Tenant-Id or X-Tenant:
        Used for context.tenant.

    X-Auth-Token:
        Used for context.auth_token.

    X-Roles:
        Used for setting context.is_admin flag to either True or False.
        The flag is set to True, if X-Roles contains either an administrator
        or admin substring. Otherwise it is set to False.
    """

    def before(self, state):
        user_id = state.request.headers.get('X-Auth-User-Id')
        user_id = state.request.headers.get('X-User', user_id)
        project_id = state.request.headers.get('X-Auth-Project-Id')
        project_id = state.request.headers.get('X-Project', project_id)
        auth_token = state.request.headers.get('X-Auth-Token', None)
        is_admin = True

        state.request.context = RequestContext(
            auth_token=auth_token,
            user_id=user_id,
            project_id=project_id,
            is_admin=is_admin)
