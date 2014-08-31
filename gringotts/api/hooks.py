#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# filename   : hooks.py
# created at : 2013-07-01 21:05:45

import re
from oslo.config import cfg
from pecan import hooks

from gringotts import exception
from gringotts.openstack.common import log
from gringotts.openstack.common import memorycache
from gringotts.context import RequestContext
from gringotts.api import acl


LOG = log.getLogger(__name__)
MC = None


def _get_cache():
    global MC
    if MC is None:
        MC = memorycache.get_client()
    return MC


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
        domain_id = state.request.headers.get('X-Domain-Id')
        auth_token = state.request.headers.get('X-Auth-Token')
        is_admin = acl.context_is_admin(state.request.headers)
        is_domain_owner = acl.context_is_domain_owner(state.request.headers)

        state.request.context = RequestContext(
            auth_token=auth_token,
            user_id=user_id,
            project_id=project_id,
            domain_id=domain_id,
            is_admin=is_admin,
            is_domain_owner=is_domain_owner)


class LimitHook(hooks.PecanHook):

    CACHE_PREFIX = "gringotts:limit"
    LIMITS = [
        #{'path': r"/v1/precharge/.*/used",
        # 'method': 'PUT',
        # 'limit': '5/h',
        # 'custom_exception': exception.PreChargeOverlimit}
    ]

    def _in_rule(self, request):
        for rule in self.LIMITS:
            if request.method == rule['method'] and re.match(rule['path'], request.path.rstrip('/')):
                return rule
        return

    def _get_expires(self, limit):
        _, unit = limit.split('/')
        if unit == 'm':
            return 60
        if unit == 'h':
            return 60 * 60
        if unit == 'd':
            return 60 * 60 * 24

    def _overlimit(self, count, rule):
        total_count, _ = rule['limit'].split('/')
        total_count = int(total_count)
        if count >= total_count:
            # overlimit
            return True
        return False

    def before(self, state):
        limit_info = {}
        limit_rule = self._in_rule(state.request)
        if not limit_rule:
            return
        LOG.debug("limit to rule" + str(limit_rule))

        limit_info['rule'] = limit_rule

        mc_key = str("%s:%s:%s:%s" % (self.CACHE_PREFIX, state.request.method,
                                      limit_rule['path'],
                                      state.request.context.project_id))
        LOG.debug('mc_key is: %s' % mc_key)
        limit_info['cache_key'] = mc_key
        state.request.limit_info = limit_info

        cache = _get_cache()
        count = cache.get(mc_key)
        if count is None:
            cache.set(mc_key, 0, self._get_expires(limit_rule['limit']))
            return

        if self._overlimit(int(count), limit_rule):
            if 'custom_exception' in limit_rule:
                raise limit_rule['custom_exception']
            raise exception.Overlimit(api=limit_rule['path'])

    def after(self, state):
        if 200 <= state.response.status_code < 300 and hasattr(state.request, 'limit_info'):
            limit_info = state.request.limit_info
            # increase user's limit count
            _get_cache().incr(limit_info['cache_key'])
