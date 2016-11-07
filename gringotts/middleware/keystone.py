from __future__ import absolute_import

import copy
import re

import webob
import logging
from oslo_config import cfg

from gringotts.client.noauth import client
from gringotts.openstack.common import jsonutils
from keystone.common import dependency
from keystone.common import driver_hints

LOG = logging.getLogger(__name__)
cfg.CONF.import_group("billing", "gringotts.middleware.base")

KEYSTONE_OPTS = [
    cfg.StrOpt('initial_balance',
               default='10',
               help="Initial balance for the new account"),
    cfg.StrOpt('initial_level',
               default='3',
               help="Initial level for the new account"),
    cfg.StrOpt('billing_endpoint',
               default='http://127.0.0.1:8975',
               help="Billing endpoint"),
    cfg.StrOpt('billing_owner_role_name',
               default='billing_owner',
               help="Billing owner role name"),
    cfg.StrOpt('billing_admin_user_name',
               default=None,
               help="Billing admin user name"),
    cfg.StrOpt('billing_admin_user_domain_name',
               default=None,
               help="Billing admin user domain name"),
]
cfg.CONF.register_opts(KEYSTONE_OPTS,group="billing")

UUID_RE = r"([0-9a-f]{32}|[0-9a-z]{8}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{12})"
API_VERSION = r"(v2.0|v3)"
USER_RESOURCE_RE = r"(users)"
PROJECT_RESOURCE_RE = r"(projects|tenants)"
ROLE_RESOURCE_RE = r"(roles|roles/OS-KSADM)"


class MiniResp(object):
    def __init__(self, error_message, env, headers=[]):
        # The HEAD method is unique: it must never return a body, even if
        # it reports an error (RFC-2616 clause 9.4). We relieve callers
        # from varying the error responses depending on the method.
        if env['REQUEST_METHOD'] == 'HEAD':
            self.body = ['']
        else:
            self.body = [error_message]
        self.headers = list(headers)
        self.headers.append(('Content-type', 'application/json'))


class User(object):

    def __init__(self, user_id, user_name, domain_id):
        self.user_id = user_id
        self.user_name = user_name
        self.domain_id = domain_id

    def as_dict(self):
        return copy.copy(self.__dict__)

class Project(object):

    def __init__(self, project_id, project_name, domain_id):
        self.project_id = project_id
        self.project_name = project_name
        self.domain_id = domain_id

    def as_dict(self):
        return copy.copy(self.__dict__)


@dependency.requires('role_api', 'resource_api', 'identity_api')
class KeystoneBillingProtocol(object):

    def __init__(self, app, conf):
        self.app = app
        self.conf = conf
        self.position = 2
        self.user_id_position = 4
        self.role_id_position = 6

        self.user_regex = re.compile(
            r"^/%s/%s/%s([.][^.]+)?$" % \
                (API_VERSION, USER_RESOURCE_RE, UUID_RE),
            re.UNICODE)
        self.create_user_regex = re.compile(
            r"^/%s/%s([.][^.]+)?$" % (API_VERSION, USER_RESOURCE_RE),
            re.UNICODE)
        self.project_regex = re.compile(
            r"^/%s/%s/%s([.][^.]+)?$" % \
                (API_VERSION, PROJECT_RESOURCE_RE, UUID_RE),
            re.UNICODE)
        self.create_project_regex = re.compile(
            r"^/%s/%s([.][^.]+)?$" % (API_VERSION, PROJECT_RESOURCE_RE),
            re.UNICODE)
        self.role_regex = re.compile(
            r"^/%s/%s/%s/%s/%s/%s/%s([.][^.]+)?$" % \
                (API_VERSION, PROJECT_RESOURCE_RE, UUID_RE, USER_RESOURCE_RE,
                 UUID_RE, ROLE_RESOURCE_RE, UUID_RE),
            re.UNICODE)

        noauth_billing_endpoint = cfg.CONF.billing.billing_endpoint + \
            '/noauth'
        self.gclient = client.Client(endpoint=noauth_billing_endpoint)

    def create_user_action(self, method, path_info):
        if method == "POST" and self.create_user_regex.search(path_info):
            return True
        return False

    def delete_user_action(self, method, path_info):
        if method == "DELETE" and self.user_regex.search(path_info):
            return True
        return False

    def create_project_action(self, method, path_info):
        if method == "POST" and self.create_project_regex.search(path_info):
            return True
        return False

    def delete_project_action(self, method, path_info):
        if method == "DELETE" and self.project_regex.search(path_info):
            return True
        return False

    def add_role_action(self, method, path_info):
        if method == "PUT" and self.role_regex.search(path_info):
            return True
        return False

    def unassign_role_action(self, method, path_info):
        if method == "DELETE" and self.role_regex.search(path_info):
            return True
        return False

    def parse_user_result(self, body, result):
        users = []
        try:
            for r in result:
                user = jsonutils.loads(r)['user']
                users.append(User(
                    user_id=user['id'],
                    user_name=user['name'],
                    domain_id=user['domain_id']))
        except Exception:
            return []
        return users

    def parse_project_result(self, body, result):
        projects = []
        try:
            for r in result:
               project = jsonutils.loads(r)['project']
               projects.append(Project(
                   project_id=project['id'],
                   project_name=project['name'],
                   domain_id=project['domain_id']))
        except Exception:
            return []
        return projects

    @property
    def billing_owner_role_id(self):
        role_name = cfg.CONF.billing.billing_owner_role_name
        hints = driver_hints.Hints()
        hints.add_filter('name', role_name)
        role = self.role_api.list_roles(hints)
        if not role:
            LOG.warn("The %s role didn't exist." % role_name)
            return None
        return role[0]['id']

    @property
    def billing_admin_user_id(self):
        user_name = cfg.CONF.billing.billing_admin_user_name
        if not user_name:
            return None
        domain_name = \
            cfg.CONF.billing.billing_admin_user_domain_name
        try:
            domain = \
                self.resource_api.get_domain_by_name(domain_name)
            domain_id = domain['id']
        except Exception as e:
            LOG.warn(e)
            return None

        try:
            user = \
                self.identity_api.get_user_by_name(user_name, domain_id)
        except Exception as e:
            LOG.warn(e)
            return None

        return user['id']

    def get_project_id(self, path_info, position):
        "Get project id from path_info"
        match = self.project_regex.search(path_info)
        if match:
            return match.groups()[position]

    def get_role_action_ids(self, path_info):
        "Get user_id, project_id and role_id from path_info"
        match = self.role_regex.search(path_info)
        if match:
            return (match.groups()[self.user_id_position],
                    match.groups()[self.position],
                    match.groups()[self.role_id_position])

    def __call__(self, env, start_response):
        request_method = env['REQUEST_METHOD']
        path_info = env.get('RAW_PATH_INFO') or env.get('REQUEST_URI')

        if not cfg.CONF.billing.enable_billing or \
                request_method in set(['GET', 'OPTIONS', 'HEAD']):
            return self.app(env, start_response)

        try:
            req = webob.Request(env)
            if req.content_length:
                body = req.json
            else:
                body = {}
        except Exception:
            body = {}

        if self.create_user_action(request_method, path_info):
            result = self.app(env, start_response)
            users = self.parse_user_result(body, result)
            for user in users:
                self.create_user(env, start_response,
                                 body, user)
            return result
        elif self.delete_user_action(request_method, path_info):
            return self.app(env, start_response)
        elif self.create_project_action(request_method, path_info):
            result = self.app(env, start_response)
            projects = self.parse_project_result(body, result)
            for project in projects:
                self.create_project(env, start_response,
                                    body, project)
            return result
        elif self.delete_project_action(request_method, path_info):
            return self.app(env, start_response)

        # Changing the billing owner of a project has two actions, and
        # the billing_owner role must exist in Kesytone.
        # Firstly, assign the billing owner role to a user on a project.
        # If the project had a billing owner previously, now the project
        # is assigned with two billing owner roles. Secondly, unassign
        # the billing owner role to the previous billing owner on the
        # project.
        elif self.add_role_action(request_method, path_info):
            user_id, project_id, role_id = self.get_role_action_ids(path_info)
            app_result = self.app(env, start_response)

            if not self._is_billing_owner_role(role_id):
                return app_result

            if not app_result[0]:
                success, result = self.add_role(env, start_response,
                                                user_id, project_id)
                if not success:
                    app_result = result
            return app_result
        elif self.unassign_role_action(request_method, path_info):
            user_id, project_id, role_id = \
                self.get_role_action_ids(path_info)

            if not self._is_billing_owner_role(role_id):
                return self.app(env, start_response)

            success, result = self.get_project(env, start_response, project_id)
            if not success:
                return result

            current_billing_owner = result['user_id']
            if current_billing_owner == user_id:
                return self._reject_request_403(env, start_response)

            return self.app(env, start_response)

        else:
            return self.app(env, start_response)

    def _is_billing_owner_role(self, role_id):
        return role_id == self.billing_owner_role_id

    def create_user(self, env, start_response, body,
                    user, balance=None, consumption=None,
                    level=None):
        balance = balance or cfg.CONF.billing.initial_balance
        consumption = consumption or 0
        level = level or cfg.CONF.billing.initial_level
        self.gclient.create_account(
            user.user_id, user.domain_id,
            balance, consumption, level)

    def create_project(self, env, start_response, body,
                       project, consumption=None):
        consumption = consumption or 0
        user_id = self.billing_admin_user_id
        self.gclient.create_project(
            project.project_id, project.domain_id,
            consumption, user_id)

    def delete_project(self, env, start_response, body,
                       project_id, region_name=None):
        try:
            self.gclient.delete_resources(project_id)
        except Exception:
            return False, self._reject_request_500(env, start_response)
        return True, None

    def add_role(self, env, start_response, user_id, project_id):
        try:
            self.gclient.change_billing_owner(
                user_id, project_id)
        except Exception:
            return False, self._reject_request_500(env, start_response)
        return True, None

    def get_project(self, env, start_response, project_id):
        try:
            result = self.gclient.get_project(project_id)
        except Exception:
            return False, self._reject_request_500(env, start_response)
        return True, result

    def _reject_request_403(self, env, start_response):
        return self._reject_request(env, start_response,
                                    "The project must have a billing owner",
                                    "403 Forbidden")

    def _reject_request_500(self, env, start_response):
        return self._reject_request(env, start_response,
                                    "Billing service error",
                                    "500 BillingServiceError")

    def _reject_request(self, env, start_response, resp_data, status_code):
        resp = MiniResp('{"msg": "%s"}' % resp_data, env)
        start_response(status_code, resp.headers)
        return resp.body


def filter_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)

    def bill_filter(app):
        return KeystoneBillingProtocol(app, conf)
    return bill_filter
