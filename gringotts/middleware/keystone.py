import re

import webob
import logging
from oslo_config import cfg

LOG = logging.getLogger(__name__)
cfg.CONF.import_group("billing", "gringotts.middleware.base")

UUID_RE = r"([0-9a-f]{32}|[0-9a-z]{8}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{12})"
API_VERSION = r"(v2.0|v3)"
USER_RESOURCE_RE = r"(users)"
PROJECT_RESOURCE_RE = r"(projects|tenants)"
ROLE_RESOURCE_RE = r"(roles|roles/OS-KSADM)"


class KeystoneBillingProtocol(object):

    def __init__(self, app, conf):
        self.app = app
        self.conf = conf

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

    def delete_role_action(self, method, path_info):
        if method == "DELETE" and self.role_regex.search(path_info):
            return True
        return False

    def __call__(self, env, start_response):
        request_method = env['REQUEST_METHOD']
        path_info = env['RAW_PATH_INFO']

        if not cfg.CONF.billing.enable_billing or \
                request_method in set(['GET', 'OPTIONS', 'HEAD']):
            return self.app(env, start_response)

        if self.create_user_action(request_method, path_info):
            result = self.app(env, start_response)
            return result
        elif self.delete_user_action(request_method, path_info):
            return self.app(env, start_response)
        elif self.create_project_action(request_method, path_info):
            result = self.app(env, start_response)
            return result
        elif self.delete_project_action(request_method, path_info):
            return self.app(env, start_response)
        elif self.add_role_action(request_method, path_info):
            result = self.app(env, start_response)
            return result
        elif self.delete_role_action(request_method, path_info):
            return self.app(env, start_response)
        else:
            return self.app(env, start_response)


def filter_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)

    def bill_filter(app):
        return KeystoneBillingProtocol(app, conf)
    return bill_filter
