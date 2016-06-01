import copy

import webob
import logging
from oslo_config import cfg
from decimal import Decimal

from gringotts.client.v2 import client
from gringotts import exception
from gringotts.openstack.common import uuidutils
from gringotts.price import pricing
from gringotts import utils


LOG = logging.getLogger(__name__)

OPTS = [
    cfg.BoolOpt('enable_billing',
                default=False,
                help="Open the billing or not"),
    cfg.StrOpt('min_balance_fip',
               default="10",
               help="The minimum balance to create a floatingip"),
    cfg.StrOpt('region_name',
               default="RegionOne",
               help="The current region name"),
]
cfg.CONF.register_opts(OPTS, group="billing")


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


class Resource(object):

    def __init__(self, resource_id, resource_name, type, status,
                 user_id, project_id):
        self.resource_id = resource_id
        self.resource_name = resource_name
        self.type = type
        self.status = status
        self.user_id = user_id
        self.project_id = project_id

    def as_dict(self):
        return copy.copy(self.__dict__)


class Collection(object):
    """Some field collection that ProductItem will use to get product or
    to create/update/delete subscription
    """
    def __init__(self, product_name, service, region_id,
                 resource_volume, user_id, project_id):
        self.product_name = product_name
        self.service = service
        self.region_id = region_id
        self.resource_volume = resource_volume
        self.user_id = user_id
        self.project_id = project_id

    def as_dict(self):
        return copy.copy(self.__dict__)


class ProductItem(object):

    service = None

    def __init__(self, gclient):
        self.gclient = gclient

    def get_product_name(self, body):
        raise NotImplementedError

    def get_resource_volume(self, body):
        return 1

    def get_collection(self, env, body):
        """Get collection from body
        """
        try:
            user_id = env['HTTP_X_USER_ID']
            project_id = env['HTTP_X_PROJECT_ID']
        except KeyError:
            user_id = env['HTTP_X_AUTH_USER_ID']
            project_id = env['HTTP_X_AUTH_PROJECT_ID']
        region_id = cfg.CONF.billing.region_name
        return Collection(product_name=self.get_product_name(body),
                          service=self.service,
                          region_id=region_id,
                          resource_volume=self.get_resource_volume(body),
                          user_id=user_id,
                          project_id=project_id)

    def create_subscription(self, env, body, order_id, type=None):
        """Subscribe to this product
        """
        collection = self.get_collection(env, body)
        result = self.gclient.create_subscription(order_id,
                                                  type=type,
                                                  **collection.as_dict())
        return result

    def get_unit_price(self, env, body, method):
        """Get product unit price"""
        collection = self.get_collection(env, body)
        product = self.gclient.get_product(collection.product_name,
                                           collection.service,
                                           collection.region_id)
        if product:
            if 'unit_price' in product:
                price_data = pricing.get_price_data(product['unit_price'],
                                                    method)
            else:
                price_data = None

            return pricing.calculate_price(
                collection.resource_volume, price_data)
        else:
            return 0


class BillingProtocol(object):
    """Middleware that handles the billing owed logic
    """
    def __init__(self, app, conf):
        self.app = app
        self.conf = conf

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

        self.black_list = [
            self.create_resource_action,
            self.delete_resource_action,
        ]
        self.resource_regexs = []
        self.resize_resource_actions = []

        # make billing client
        self.gclient = client.Client(username=self.admin_user,
                                     password=self.admin_password,
                                     project_name=self.admin_tenant_name,
                                     auth_url=self.auth_url)

    def _parse_bill_params_from_querystring(self, env):
        query_string = env.get('QUERY_STRING')
        bill_params = {}
        if query_string:
            copy_query_string = query_string.split("&")
            new_query_string = query_string.split("&")
            for qs in copy_query_string:
                key, value = qs.split("=")
                if key.startswith("bill"):
                    bill_params[key] = value
                    new_query_string.remove(qs)
            env['QUERY_STRING'] = "&".join(new_query_string)
        return bill_params

    def _parse_bill_params_from_body(self, body):
        return body.get("billing", {})

    def _validate_bill_params(self, env, start_response, bill_params):
        """Validate bill params

        There are three billing params for now:
        * bill_method, string, valid values are: hour, month, year
        * bill_period, integer, useful when bill_method is month or year
        * bill_renew, bool, default is false, useful when bill_method
          is month or year

        There are two special cases:
        * If not specify any billing params, the default bill_method is hour.
        * If specify bill_method is month or year, then must specify
          bill_period
        """
        result = dict(bill_method=None, bill_period=None, bill_renew=None)

        if not bill_params.get('bill_method'):  # None or not specified
            result['bill_method'] = 'hour'
            return True, result

        bill_method = bill_params['bill_method'].lower()
        if bill_method not in ['hour', 'month', 'year']:
            msg = "bill_method %s" % bill_method
            return False, self._reject_request_400(env, start_response, msg)
        result['bill_method'] = bill_method

        if bill_method in ['month', 'year']:
            bill_period = bill_params.get('bill_period')
            try:
                bill_period = int(bill_period)  # can convert to int
                if bill_period <= 0:
                    raise ValueError
            except ValueError:
                msg = "bill_period %s" % bill_period
                return False, self._reject_request_400(env, start_response, msg)
            result['bill_period'] = bill_period

            bill_renew = bill_params.get('bill_renew') or False
            try:
                bill_renew = utils.true_or_false(bill_renew)
            except ValueError:
                msg = "bill_renew %s" % bill_renew
                return False, self._reject_request_400(env, start_response, msg)
            result['bill_renew'] = bill_renew
        return True, result

    def __call__(self, env, start_response):
        """Handle incoming request.

        Reject request if the account is owed
        """
        request_method = env['REQUEST_METHOD']
        path_info = env['PATH_INFO']
        roles = env['HTTP_X_ROLES'].split(',')

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

        if not self.check_if_in_blacklist(request_method, path_info, body):
            return self.app(env, start_response)

        min_balance = "0"
        try:
            user_id = env['HTTP_X_USER_ID']
            project_id = env['HTTP_X_PROJECT_ID']
        except KeyError:
            user_id = env['HTTP_X_AUTH_USER_ID']
            project_id = env['HTTP_X_AUTH_PROJECT_ID']

        if self.create_resource_action(request_method, path_info, body):
            # parse and validate bill parameters
            bill_params = self._parse_bill_params_from_body(body)
            if not bill_params:
                bill_params = self._parse_bill_params_from_querystring(env)
            success, result = self._validate_bill_params(env, start_response,
                                                         bill_params)
            if not success:
                return result
            bill_params = result

            if bill_params['bill_method'] == 'hour':
                if request_method == "POST" \
                        and ("floatingips" in path_info or
                             'floatingipsets' in path_info):
                    min_balance = cfg.CONF.billing.min_balance_fip

                success, result = self.check_if_owed(env, start_response,
                                                     project_id, min_balance)
                if not success:
                    return result

                unit = 'hour'
                unit_price = self.get_order_unit_price(env, body, unit)
                # Additional properties are not allowed by Nova API
                if 'billing' in body:
                    body.pop('billing')
                    req.json = body
                app_result = self.app(env, start_response)
                resources = self.parse_app_result(body, app_result,
                                                  user_id, project_id)

                for resource in resources:
                    self.create_order(env, start_response, body,
                                      unit_price, unit,
                                      None, None,
                                      resource)

                return app_result
            else:
                renew = bill_params['bill_renew']
                unit = bill_params['bill_method']
                unit_price = self.get_order_unit_price(env, body, unit)

                period = bill_params['bill_period']
                success, result = self.get_resource_count(body)
                if not success:
                    return self._reject_request_400(env, start_response, result)
                count = result

                total_price = str(unit_price * period * count)

                success, result = self.freeze_balance(env, start_response,
                                                      project_id, total_price)
                if not success:
                    return result

                # NOTE(suo): This is a flag to identify the resource's billing
                # method in notification. For now, this is a hack to put the flag
                # in to the role list, because only the HTTP_X_ROLES is extenable
                # and contained in notification message. When gring-waiter receive
                # the notification, if it contains month_billing in roles list, it
                # will do nothing, because gring-waiter only handles the hourly
                # billing resource. After gringotts is centralized, this will be
                # removed. And this requires billing middleware places before the
                # keystonecontext middleware in api-paste.ini
                env['HTTP_X_ROLES'] = env['HTTP_X_ROLES'] + ',month_billing'
                env['HTTP_X_ROLE'] = env['HTTP_X_ROLE'] + ',month_billing'
                app_result = self.app(env, start_response)
                resources = self.parse_app_result(body, app_result,
                                                  user_id, project_id)

                if not resources:
                    success, result = self.unfreeze_balance(
                        env, start_response, project_id, total_price)
                    # If not success, should not create order
                    if not success:
                        return app_result
                else:
                    for resource in resources:
                        self.create_order(env, start_response, body,
                                          unit_price, unit,
                                          period, renew, resource)
                return app_result
        else:
            resource_id = self.get_resource_id(path_info, self.position)

            # FIXME(suo): If there is no order, the resource should also
            # can be deleted?
            success, result = self.get_order_by_resource_id(
                env, start_response, resource_id)
            if not success:
                return self.app(env, start_response)

            order = result

            if self.delete_resource_action(request_method, path_info, body):
                # user can delete resource billed by hour directly
                if not order.get('unit') or order.get('unit') == 'hour':
                    self.delete_resource_order(env,
                                               start_response,
                                               order['order_id'],
                                               order['type'])
                    return self.app(env, start_response)

                # normal user can't delete resoruces billed by month/year
                admin_roles = ['admin', 'uos_admin']
                if not any(role in admin_roles for role in roles):
                    return self._reject_request_403(env, start_response)

                # only admin can delete resources billed by month/year
                success, result = self.close_order(env, start_response,
                                                   order['order_id'])
                if not success:
                    return result

                return self.app(env, start_response)

            elif self.resize_resource_action(request_method, path_info, body):
                # by-hour resource can be operated directly
                if not order.get('unit') or order.get('unit') == 'hour':
                    min_balance = "0"
                    success, result = self.check_if_owed(env, start_response,
                                                         project_id, min_balance)
                    if not success:
                        return result

                    success, result = self.resize_resource_order(env,
                                                                 body,
                                                                 start_response,
                                                                 order.get('order_id'),
                                                                 order.get('resource_id'),
                                                                 order.get('type'))
                    return self.app(env, start_response)

                # can't change resoruce billed by month/year for now
                return self._reject_request_403(env, start_response)

            else:
                # by-hour resource only can be operated when the balance is sufficient
                if not order.get('unit') or order.get('unit') == 'hour':
                    min_balance = "0"
                    success, result = self.check_if_owed(env, start_response,
                                                         project_id, min_balance)
                    if not success:
                        return result
                    return self.app(env, start_response)

                # owed monthly billing resource can't be operated
                if order['owed']:
                    return self._reject_request_403(env, start_response)

                # not owed monthly billing resource can be operated directly
                env['HTTP_X_ROLES'] = env['HTTP_X_ROLES'] + ',month_billing'
                env['HTTP_X_ROLE'] = env['HTTP_X_ROLE'] + ',month_billing'
                return self.app(env, start_response)

    def check_if_in_blacklist(self, method, path_info, body):
        for black_method in self.black_list:
            if black_method(method, path_info, body):
                return True
        return False

    def check_if_owed(self, env, start_response, project_id, min_balance):
        try:
            account = self.gclient.get_billing_owner(project_id)
            if account['level'] == 9:
                return True, False
            if Decimal(str(account['balance'])) <= Decimal(min_balance):
                LOG.warn('The billing owner of project %s is owed' % project_id)
                return False, self._reject_request_402(env, start_response,
                                                       min_balance)
            return True, False
        except exception.HTTPNotFound:
            msg = 'Can not find the project: %s' % project_id
            LOG.exception(msg)
            return False, self._reject_request_404(
                env, start_response, "Project %s" % project_id)
        except Exception as e:
            msg = 'Unable to get account info from billing service, ' \
                  'for the reason: %s' % e
            LOG.exception(msg)
            return False, self._reject_request_500(env, start_response)

    def freeze_balance(self, env, start_response, project_id, total_price):
        try:
            account = self.gclient.freeze_balance(project_id, total_price)
            return True, False
        except exception.PaymentRequired:
            LOG.warn("The balance of the billing owner of "
                     "the project %s is not sufficient" % project_id)
            return False, self._reject_request_402(env, start_response,
                                                   total_price)
        except exception.HTTPNotFound:
            msg = 'Can not find the project: %s' % project_id
            LOG.exception(msg)
            return False, self._reject_request_404(
                env, start_response, "Project %s" % project_id)
        except Exception as e:
            msg = 'Unable to freeze balance for the project %s, ' \
                  'for the reason: %s' % (project_id, e)
            LOG.exception(msg)
            return False, self._reject_request_500(env, start_response)

    def unfreeze_balance(self, env, start_response, project_id, total_price):
        """Unfreeze the balance that was frozen before creating resource
        if failed to create the resource for some reason.
        """
        try:
            account = self.gclient.unfreeze_balance(project_id, total_price)
            return True, False
        except exception.PaymentRequired:
            LOG.warn("The frozen balance of the billing owner of "
                     "the project %s is not sufficient" % project_id)
            return False, self._reject_request_402(env, start_response,
                                                   total_price)
        except exception.HTTPNotFound:
            msg = 'Can not find the project: %s' % project_id
            LOG.exception(msg)
            return False, self._reject_request_404(
                env, start_response, "Project %s" % project_id)
        except Exception as e:
            msg = 'Unable to unfreeze balance for the project %s, ' \
                  'for the reason: %s' % (project_id, e)
            LOG.exception(msg)
            return False, self._reject_request_500(env, start_response)

    def create_order(self, env, start_response, body,
                     unit_price, unit, period, renew, resource):
        """Create an order for resource created

        1. Create subscriptions of this order
        2. Create order, can create cron job in the request
           create order
        """
        order_id = uuidutils.generate_uuid()

        # Create subscriptions for this order
        for ext in self.product_items.extensions:
            state = ext.name.split('_')[0]
            ext.obj.create_subscription(env, body, order_id, type=state)

        self.gclient.create_order(order_id,
                                  cfg.CONF.billing.region_name,
                                  unit_price,
                                  unit,
                                  period=period,
                                  renew=renew,
                                  **resource.as_dict())

    def close_order(self, env, start_response, order_id):
        try:
            self.gclient.close_order(order_id)
            return True, None
        except Exception as e:
            msg = "Unable to close the order: %s" % order_id
            LOG.exception(msg)
            return False, self._reject_request_500(env, start_response)

    def get_order_by_resource_id(self, env, start_response, resource_id):
        try:
            order = self.gclient.get_order_by_resource_id(resource_id)
            return True, order
        except exception.HTTPNotFound:
            msg = 'Can not find the order of the resource: %s' % resource_id
            LOG.exception(msg)
            return False, self._reject_request_404(
                env, start_response, "Order of the resource %s" % resource_id)
        except Exception as e:
            msg = 'Unable to get the order of the resource: %s, ' \
                  'for the reason: %s' % (resource_id, e)
            LOG.exception(msg)
            return False, self._reject_request_500(env, start_response)

    def get_order_unit_price(self, env, body, method):
        """Caculate unit price of this order
        """
        unit_price = 0
        for ext in self.product_items.extensions:
            if ext.name.startswith('running'):
                price = ext.obj.get_unit_price(env, body, method)
                unit_price += price
        return unit_price

    def get_resource_count(self, body):
        return True, 1

    def delete_resource_order(self, env, start_response, order_id, resource_type):
        try:
            self.gclient.delete_resource_order(order_id, resource_type)
        except Exception as e:
            msg = "Unable to delete the order: %s" % order_id
            LOG.exception(msg)
            return False, self._reject_request_500(env, start_response)

    def parse_app_result(self, body, result, user_id, project_id):
        """Parse response that processed by application/middleware

        Parse the result to a list contains resource_id and resource_name
        """
        raise NotImplementedError()

    def create_resource_action(self, method, path_info, body):
        if method == "POST" and self.create_resource_regex.search(path_info):
            return True
        return False

    def delete_resource_action(self, method, path_info, body):
        if method == 'DELETE' and self.resource_regex.search(path_info):
            return True
        return False

    def resize_resource_action(self, method, path_info, body):
        """The action that change the configuration of the resource."""
        for action in self.resize_resource_actions:
            if action(method, path_info, body):
                return True
        return False

    def get_resource_id(self, path_info, position):
        """Get resource id from various path_info"""
        for resource_regex in self.resource_regexs:
            match = resource_regex.search(path_info)
            if match:
                return match.groups()[position]

    def _reject_request_400(self, env, start_response, what):
        return self._reject_request(
            env, start_response,
            "Invalid billing parameters, " + what,
            "400 InvalidBillingParameters")

    def _reject_request_401(self, env, start_response):
        return self._reject_request(
            env, start_response,
            "Billing authentication failed",
            "401 Unauthorized")

    def _reject_request_402(self, env, start_response, min_balance):
        """For 402 condition:
        * if the minimum balance is 0, which is the most cases
        * if the minimum balance is 10, which is used for floatingip for now.
        """
        return self._reject_request(
            env, start_response,
            "Payment required, min_balance is %s" % min_balance,
            "402 PaymentRequired")

    def _reject_request_403(self, env, start_response):
        return self._reject_request(env, start_response,
                                    "Not authorized",
                                    "403 NotAuthorized")

    def _reject_request_404(self, env, start_response, what):
        return self._reject_request(env, start_response,
                                    what + " not found",
                                    "404 NotFound")

    def _reject_request_500(self, env, start_response):
        return self._reject_request(env, start_response,
                                    "Billing service error",
                                    "500 BillingServiceError")

    def _reject_request(self, env, start_response, resp_data, status_code):
        resp = MiniResp('{"msg": "%s"}' % resp_data, env)
        start_response(status_code, resp.headers)
        return resp.body

    def _conf_get(self, name):
        # try config from paste-deploy first
        if name in self.conf:
            return self.conf[name]
        try:
            return cfg.CONF.keystone_authtoken[name]
        except cfg.NoSuchOptError:
            return None
