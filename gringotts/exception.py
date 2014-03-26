# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Gringotts base exception handling.

Includes decorator for re-raising Gringotts-type exceptions.

SHOULD include dedicated exception logging.

"""

from oslo.config import cfg
import six

from gringotts.openstack.common.gettextutils import _
from gringotts.openstack.common import log as logging


LOG = logging.getLogger(__name__)

exc_log_opts = [
    cfg.BoolOpt('fatal_exception_format_errors',
                default=False,
                help='make exception message format errors fatal'),
]

CONF = cfg.CONF
CONF.register_opts(exc_log_opts)


class GringottsException(Exception):
    """Base Gringotts Exception

    To correctly use this class, inherit from it and define
    a 'message' property. That message will get printf'd
    with the keyword arguments provided to the constructor.

    """
    message = _("An unknown exception occurred.")
    code = 500
    headers = {}
    safe = False

    def __init__(self, message=None, **kwargs):
        self.kwargs = kwargs

        if 'code' not in self.kwargs:
            try:
                self.kwargs['code'] = self.code
            except AttributeError:
                pass

        if not message:
            try:
                message = self.message % kwargs

            except Exception as e:
                # kwargs doesn't match a variable in the message
                # log the issue and the kwargs
                LOG.exception(_('Exception in string format operation'))
                for name, value in kwargs.iteritems():
                    LOG.error("%s: %s" % (name, value))

                if CONF.fatal_exception_format_errors:
                    raise e
                else:
                    # at least get the core message out if something happened
                    message = self.message

        super(GringottsException, self).__init__(message)

    def format_message(self):
        if self.__class__.__name__.endswith('_Remote'):
            return self.args[0]
        else:
            return six.text_type(self)


class NotAuthorized(GringottsException):
    message = _("Not authorized.")
    code = 403


class NotSufficientFund(GringottsException):
    message = _("The user %(project_id)s balance is not sufficient")
    code = 400


class AdminRequired(NotAuthorized):
    message = _("User does not have admin privileges")


class PolicyNotAuthorized(NotAuthorized):
    message = _("Policy doesn't allow %(action)s to be performed.")


class OperationNotPermitted(NotAuthorized):
    message = _("Operation not permitted.")


class MissingRequiredParams(GringottsException):
    message = _("Missing required parameters: %(reason)s")
    code = 400


class DBError(GringottsException):
    message = _("Error in DB backend: %(reason)s")


class DuplicatedProduct(GringottsException):
    message = _("Duplicated Product: %(reason)s")


class Invalid(GringottsException):
    message = _("Unacceptable parameters.")
    code = 400


class InvalidChargeValue(Invalid):
    message = _("The charge value %(value)s is invalid.")


class InvalidUUID(Invalid):
    message = _("Expected a uuid but received %(uuid)s.")


class InvalidIdentity(Invalid):
    message = _("Expected an uuid or int but received %(identity)s.")


class ImageUnacceptable(GringottsException):
    message = _("Image %(image_id)s is unacceptable: %(reason)s")


class InstanceStateError(GringottsException):
    message = _("The state of the instance %(instance_id)s is %(state)s")


class VolumeStateError(GringottsException):
    message = _("The state of the volume %(volume_id)s is %(state)s")


# Cannot be templated as the error syntax varies.
# msg needs to be constructed when raised.
class InvalidParameterValue(Invalid):
    message = _("%(err)s")


class NotFound(GringottsException):
    message = _("Resource could not be found.")
    code = 404


class AccountNotFound(NotFound):
    message = _("Account %(project_id)s could not be found")


class AccountCreateFailed(GringottsException):
    message = _("Fail to create account for the project %(project_id)s")


class BillCreateFailed(GringottsException):
    message = _("Fail to create bill for the order: %(order_id)s")


class BillCloseFailed(GringottsException):
    message = _("Fail to close bill for the order: %(order_id)s")


class OrderBillsNotFound(NotFound):
    message = _("Order %(order_id)s bills could not be found")


class ResourceOrderNotFound(NotFound):
    message = _("The order of the resource %(resource_id)s not found")


class OrderNotFound(NotFound):
    message = _("Order %(order_id)s bills not found")


class ProductIdNotFound(NotFound):
    message = _("Product %(product_id)s could not be found")


class ProductNameNotFound(NotFound):
    message = _("Product %(product_name)s could not be found")


class MarkerNotFound(NotFound):
    message = _("Marker %(marker)s could not be found")


class LatestBillNotFound(NotFound):
    message = _("Can't find latest bill for order: %s(order_id)s")


class OwedBillsNotFound(NotFound):
    message = _("Can't find owed bills for order: %s(order_id)s")


class DiskNotFound(NotFound):
    message = _("No disk at %(location)s")


class DriverNotFound(NotFound):
    message = _("Failed to load driver %(driver_name)s.")


class ImageNotFound(NotFound):
    message = _("Image %(image_id)s could not be found.")


class HostNotFound(NotFound):
    message = _("Host %(host)s could not be found.")


class FileNotFound(NotFound):
    message = _("File %(file_path)s could not be found.")


class NoValidHost(NotFound):
    message = _("No valid host was found. %(reason)s")


class InstanceNotFound(NotFound):
    message = _("Instance %(instance)s could not be found.")


class GlanceConnectionFailed(GringottsException):
    message = _("Connection to glance host %(host)s:%(port)s failed: "
                "%(reason)s")


class ImageNotAuthorized(NotAuthorized):
    message = _("Not authorized for image %(image_id)s.")


class InvalidImageRef(Invalid):
    message = _("Invalid image href %(image_href)s.")


class CatalogUnauthorized(GringottsException):
    message = _("Unauthorised for keystone service catalog.")


class CatalogFailure(GringottsException):
    pass


class CatalogNotFound(GringottsException):
    message = _("Attr %(attr)s with value %(value)s not found in keystone "
                "service catalog.")


class ServiceUnavailable(GringottsException):
    message = _("Connection failed")


class HTTPException(GringottsException):
    message = _("Requested version of OpenStack Images API is not available.")


class InvalidEndpoint(GringottsException):
    message = _("The provided endpoint is invalid")


class CommunicationError(GringottsException):
    message = _("Unable to communicate with the server.")


class ConfigNotFound(GringottsException):
    message = _("Could not find config at %(path)s")


# The following exceptions come from novaclient.exceptions
class UnsupportedVersion(Exception):
    """Indicates that the user is trying to use an unsupported
    version of the API.
    """
    pass


class CommandError(Exception):
    pass


class AuthorizationFailure(Exception):
    pass


class NoUniqueMatch(Exception):
    pass


class AuthSystemNotFound(Exception):
    """When the user specify a AuthSystem but not installed."""
    def __init__(self, auth_system):
        self.auth_system = auth_system

    def __str__(self):
        return "AuthSystemNotFound: %s" % repr(self.auth_system)


class NoTokenLookupException(Exception):
    """This form of authentication does not support looking up
       endpoints from an existing token.
    """
    pass


class EndpointNotFound(Exception):
    """Could not find Service or Region in Service Catalog."""
    pass


class EmptyCatalog(EndpointNotFound):
    pass


class AmbiguousEndpoints(Exception):
    """Found more than one matching endpoint in Service Catalog."""
    def __init__(self, endpoints=None):
        self.endpoints = endpoints

    def __str__(self):
        return "AmbiguousEndpoints: %s" % repr(self.endpoints)


class ConnectionRefused(Exception):
    """
    Connection refused: the server refused the connection.
    """
    def __init__(self, response=None):
        self.response = response

    def __str__(self):
        return "ConnectionRefused: %s" % repr(self.response)


class ConnectionError(Exception):
    pass


class SSLError(Exception):
    pass


class Timeout(Exception):
    pass


class ClientException(Exception):
    """
    The base exception class for all exceptions this library raises.
    """
    def __init__(self, code, message=None, details=None, request_id=None,
                 url=None, method=None):
        self.code = code
        self.message = message or self.__class__.message
        self.details = details
        self.request_id = request_id
        self.url = url
        self.method = method

    def __str__(self):
        formatted_string = "%s (HTTP %s)" % (self.message, self.code)
        if self.request_id:
            formatted_string += " (Request-ID: %s)" % self.request_id

        return formatted_string


class BadRequest(ClientException):
    """
    HTTP 400 - Bad request: you sent some malformed data.
    """
    http_status = 400
    message = "Bad request"


class Unauthorized(ClientException):
    """
    HTTP 401 - Unauthorized: bad credentials.
    """
    http_status = 401
    message = "Unauthorized"


class Forbidden(ClientException):
    """
    HTTP 403 - Forbidden: your credentials don't give you access to this
    resource.
    """
    http_status = 403
    message = "Forbidden"


class HTTPNotFound(ClientException):
    """
    HTTP 404 - Not found
    """
    http_status = 404
    message = "Not found"


class MethodNotAllowed(ClientException):
    """
    HTTP 405 - Method Not Allowed
    """
    http_status = 405
    message = "Method Not Allowed"


class Conflict(ClientException):
    """
    HTTP 409 - Conflict
    """
    http_status = 409
    message = "Conflict"


class OverLimit(ClientException):
    """
    HTTP 413 - Over limit: you're over the API limits for this time period.
    """
    http_status = 413
    message = "Over limit"

    def __init__(self, *args, **kwargs):
        try:
            self.retry_after = int(kwargs.pop('retry_after'))
        except (KeyError, ValueError):
            self.retry_after = 0

        super(OverLimit, self).__init__(*args, **kwargs)


class RateLimit(OverLimit):
    """
    HTTP 429 - Rate limit: you've sent too many requests for this time period.
    """
    http_status = 429
    message = "Rate limit"


# NotImplemented is a python keyword.
class HTTPNotImplemented(ClientException):
    """
    HTTP 501 - Not Implemented: the server does not support this operation.
    """
    http_status = 501
    message = "Not Implemented"


# In Python 2.4 Exception is old-style and thus doesn't have a __subclasses__()
# so we can do this:
#     _code_map = dict((c.http_status, c)
#                      for c in ClientException.__subclasses__())
#
# Instead, we have to hardcode it:
_error_classes = [BadRequest, Unauthorized, Forbidden, HTTPNotFound,
                  MethodNotAllowed, Conflict, OverLimit, RateLimit,
                  HTTPNotImplemented]
_code_map = dict((c.http_status, c) for c in _error_classes)


def from_response(response, body, url, method=None):
    """
    Return an instance of an ClientException or subclass
    based on an requests response.

    Usage::

        resp, body = requests.request(...)
        if resp.status_code != 200:
            raise exception_from_response(resp, rest.text)
    """
    kwargs = {
        'code': response.status_code,
        'method': method,
        'url': url,
        'request_id': None,
    }

    if response.headers:
        kwargs['request_id'] = response.headers.get('x-compute-request-id')

        if 'retry-after' in response.headers:
            kwargs['retry_after'] = response.headers.get('retry-after')

    if body:
        message = "n/a"
        details = "n/a"

        if hasattr(body, 'keys'):
            error = body[list(body)[0]]
            message = error.get('message', None)
            details = error.get('details', None)

        kwargs['message'] = message
        kwargs['details'] = details

    cls = _code_map.get(response.status_code, ClientException)
    return cls(**kwargs)
