import webob
import logging
from oslo.config import cfg
from decimal import Decimal

from gringotts.client import client
from gringotts import exception


OPTS = [
    cfg.BoolOpt('enable_billing',
                default=False,
                help="Open the billing or not")
]


cfg.CONF.register_opts(OPTS, group="billing")


class AuthorizationFailure(Exception):
    pass


class ServiceError(Exception):
    pass


class AccountNotFound(Exception):
    pass


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
        self.headers.append(('Content-type', 'text/plain'))


class BillingProtocol(object):
    """Middleware that handles the billing owed logic
    """
    def __init__(self, app, conf):
        self.app = app
        self.conf = conf
        self.LOG = logging.getLogger(conf.get('log_name', __name__))

        identity_uri = self._conf_get('identity_uri')
        if not identity_uri:
            auth_host = self._conf_get('auth_host')
            auth_port = self._conf_get('auth_port')
            auth_protocol = self._conf_get('auth_protocol')
            identity_uri = '%s://%s:%s' % (auth_protocol, auth_host,
                                           auth_port)
        else:
            identity_uri = identity_uri.rstrip('/')

        # force to use v3 api
        self.auth_url = '%s/v3' % identity_uri
        self.admin_user = self._conf_get('admin_user')
        self.admin_password = self._conf_get('admin_password')
        self.admin_tenant_name = self._conf_get('admin_tenant_name')

        self.client = None

    def __call__(self, env, start_response):
        """Handle incoming request.

        Reject request if the account is owed
        """
        request_method = env['REQUEST_METHOD']
        path_info = env['PATH_INFO']

        if not cfg.CONF.billing.enable_billing or \
                request_method in set(['GET', 'OPTIONS', 'HEAD', 'DELETE']):
            return self.app(env, start_response)

        try:
            project_id = env['HTTP_X_PROJECT_ID']
        except KeyError:
            project_id = env['HTTP_X_AUTH_PROJECT_ID']

        req = webob.Request(env)
        if req.content_length:
            body = req.json
        else:
            body = {}

        if not self.check_if_in_blacklist(request_method, path_info, body):
            return self.app(env, start_response)

        self.LOG.debug('Checking if the account(%s) is owed' % project_id)

        retry = False

        try:
            self.make_billing_client()
            if self.check_if_owed(project_id):
                return self._reject_request(env, start_response, 402)
        except AuthorizationFailure:
            retry = True
        except AccountNotFound:
            return self._reject_request(env, start_response, 404)
        except ServiceError:
            return self._reject_request(env, start_response, 500)

        if retry:
            try:
                self.make_billing_client(refresh=True)
                if self.check_if_owed(project_id):
                    return self._reject_request(env, start_response, 402)
            except AuthorizationFailure:
                return self._reject_request(env, start_response, 401)
            except AccountNotFound:
                return self._reject_request(env, start_response, 404)
            except ServiceError:
                return self._reject_request(env, start_response, 500)

        return self.app(env, start_response)

    def check_if_in_blacklist(self, method, path_info, body):
        for black_method in self.black_list:
            if black_method(method, path_info, body):
                return True
        return False

    def make_billing_client(self, refresh=False):
        try:
            if not self.client or refresh:
                self.client = client.Client(username=self.admin_user,
                                            password=self.admin_password,
                                            project_name=self.admin_tenant_name,
                                            auth_url=self.auth_url)
        except (exception.Unauthorized, exception.AuthorizationFailure):
            self.LOG.error("Billing Authorization Failed - rejecting request")
            raise AuthorizationFailure("Billing Authorization Failed")
        except Exception as e:
            msg = 'Fail to initialize the billing client, for the reason: %s' % e
            self.LOG.error(msg)
            raise ServiceError(msg)

    def check_if_owed(self, project_id):
        try:
            resp, body = self.client.get('/accounts/%s' % project_id)
            if body['level'] == 9:
                return False
            if Decimal(str(body['balance'])) <= 0:
                self.LOG.warn('The account %s is owed' % project_id)
                return True
            return False
        except (exception.Unauthorized, exception.AuthorizationFailure):
            self.LOG.error("Authorization Failed - rejecting request")
            raise AuthorizationFailure("Authorization Failed")
        except exception.HTTPNotFound:
            msg = 'Can not find the account: %s' % project_id
            self.LOG.error(msg)
            raise AccountNotFound(msg)
        except Exception as e:
            msg = 'Unable to get account info from billing service, ' \
                  'for the reason: %s' % e
            self.LOG.error(msg)
            raise ServiceError(msg)

    def _reject_request(self, env, start_response, code):
        error_message = {
            401: ("Authentication Required", "401 Unauthorized"),
            402: ("Payment Required", "402 PaymentRequired"),
            404: ("Account NotFound", "404 AccountNotFound"),
            500: ("Billing Service Error", "500 BillingServiceError"),
        }
        resp = MiniResp(error_message[code][0], env)
        start_response(error_message[code][1], resp.headers)
        return resp.body

    def _conf_get(self, name):
        # try config from paste-deploy first
        if name in self.conf:
            return self.conf[name]
        try:
            return cfg.CONF.keystone_authtoken[name]
        except cfg.NoSuchOptError:
            return None
