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
import itertools
import six

from gringotts.openstack.common.gettextutils import _


exc_log_opts = [
    cfg.BoolOpt('gring_fatal_exception_format_errors',
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
                if CONF.gring_fatal_exception_format_errors:
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


class ConnectionError(GringottsException):
    """Something went wrong trying to connect to a server"""


class Timeout(GringottsException):
    """The request time out"""


class SSLError(GringottsException):
    """The request ssl error"""


class PreChargeException(GringottsException):
    """PreCharge failed
    """

class InvalidOutputFormat(GringottsException):
    message = _("Invalid output format: %(output_format)s")
    code = 400


class PreChargeHasDispatched(GringottsException):
    message = _("Precharge %(precharge_code)s has been dispatched")
    code = 400


class PreChargeHasUsed(GringottsException):
    message = _("Precharge %(precharge_code)s has been used")
    code = 400


class PreChargeHasExpired(GringottsException):
    message = _("Precharge %(precharge_code)s has been expired")
    code = 400


class InvalidQuotaParameter(GringottsException):
    message = _("Must specify project_id and region_name in request body")
    code = 400


class InvalidDeductParameter(GringottsException):
    message = _("Must specify reqId, accountNum, money and extdata.order_id")
    code = 400


class Overlimit(GringottsException):
    code = 423
    message = _("%(api)s is called overlimited")


class PreChargeOverlimit(Overlimit):
    message = _("Precharge has reached the maxium number")


class NotAuthorized(GringottsException):
    message = _("Not authorized.")
    code = 403


class EmptyCatalog(GringottsException):
    message = _("The service catalog is empty.")


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


class DuplicatedDeduct(GringottsException):
    message = _("Duplicated deduct req_id: %(req_id)s")
    code = 400


class DeductError(GringottsException):
    message = _("Deduct Failed: account: %(user_id)s, money: %(money)s, req_id: %(req_id)s")


class GetBalanceFailed(GringottsException):
    message = _("Fail to get balance of the account: %(user_id)s")


class Invalid(GringottsException):
    message = _("Unacceptable parameters.")
    code = 400


class InvalidChargeValue(Invalid):
    message = _("The charge value %(value)s is invalid.")


class InvalidTransferMoneyValue(Invalid):
    message = _("The transfer money value %(value)s is invalid.\
            Should't greater than total balance")


class NoBalanceToTransfer(Invalid):
    message = _("The balance value is %(value)s,not enough to transfer")


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


class EndpointNotFound(NotFound):
    message = _("%(endpoint_type)s endpoint for %(service_type)s not found")
    code = 404


class AccountNotFound(NotFound):
    message = _("Account %(user_id)s not found")


class DeductNotFound(NotFound):
    message = _("Deduct req_id %(req_id)s not found")


class AccountByProjectNotFound(NotFound):
    message = _("Account %(project_id)s could not be found")


class PreChargeNotFound(NotFound):
    message = _("Precharge %(precharge_code)s not found")


class AccountCreateFailed(GringottsException):
    message = _("Fail to create account %(user_id)s for the domain %(domain_id)s")


class AccountChargeFailed(GringottsException):
    message = _("Fail to charge %(value)s to account %(user_id)s")


class ProjectNotFound(NotFound):
    message = _("Project %(project_id)s could not be found")


class UserProjectNotFound(NotFound):
    message = _("Relationship between User %(user_id)s and Project %(project_id)s not found")


class ProjectCreateFailed(GringottsException):
    message =_("Fail to create project %(project_id)s with project_owner %(user_id)s")


class NotSufficientFund(GringottsException):
    message = _("Account: %(project_id)s is owed")
    code = 402

    def __init__(self, message=None, **kwargs):
        self.user_id = kwargs.get('user_id')
        self.project_id = kwargs.get('project_id')
        self.resource_id = kwargs.get('resource_id')
        super(NotSufficientFund, self).__init__(message, **kwargs)


class AccountHasOwed(GringottsException):
    message = _("Account %(project_id)s has owed")
    code = 402

    def __init__(self, message=None, **kwargs):
        self.user_id = kwargs.get('user_id')
        self.project_id = kwargs.get('project_id')
        self.resource_id = kwargs.get('resource_id')
        super(AccountHasOwed, self).__init__(message, **kwargs)


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


class SalesIdNotFound(NotFound):
    message = _("Sales whose sales_id is %(sales_id)s could not be found")


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


class HTTPException(GringottsException):
    message = _("Requested version of OpenStack Images API is not available.")


class InvalidEndpoint(GringottsException):
    message = _("The provided endpoint is invalid")


class CommunicationError(GringottsException):
    message = _("Unable to communicate with the server.")


class ConfigNotFound(GringottsException):
    message = _("Could not find config at %(path)s")


# Copy from keystoneclient.apiclient.exceptions
class HTTPError(Exception):
    """The base exception class for all HTTP exceptions.
    """
    http_status = 0
    message = "HTTP Error"

    def __init__(self, message=None, details=None,
                 response=None, request_id=None,
                 url=None, method=None, http_status=None,
                 user_id=None, project_id=None, owed=None):
        self.http_status = http_status or self.http_status
        self.message = message or self.message
        self.details = details
        self.request_id = request_id
        self.response = response
        self.url = url
        self.method = method
        self.user_id = user_id
        self.project_id = project_id
        self.owed = owed
        formatted_string = "%(message)s (HTTP %(status)s)" % {
            "message": self.message, "status": self.http_status}
        if request_id:
            formatted_string += " (Request-ID: %s)" % request_id
        super(HTTPError, self).__init__(formatted_string)


class HTTPClientError(HTTPError):
    """Client-side HTTP error.

    Exception for cases in which the client seems to have erred.
    """
    message = "HTTP Client Error"


class HTTPServerError(HTTPError):
    """Server-side HTTP error.

    Exception for cases in which the server is aware that it has
    erred or is incapable of performing the request.
    """
    message = "HTTP Server Error"


class BadRequest(HTTPClientError):
    """HTTP 400 - Bad Request.

    The request cannot be fulfilled due to bad syntax.
    """
    http_status = 400
    message = "Bad Request"


class Unauthorized(HTTPClientError):
    """HTTP 401 - Unauthorized.

    Similar to 403 Forbidden, but specifically for use when authentication
    is required and has failed or has not yet been provided.
    """
    http_status = 401
    message = "Unauthorized"


class AuthorizationFailure(HTTPClientError):
    """HTTP 401 - Unauthorized.

    Similar to 403 Forbidden, but specifically for use when authentication
    is required and has failed or has not yet been provided.
    """
    http_status = 401
    message = "Unauthorized"


class PaymentRequired(HTTPClientError):
    """HTTP 402 - Payment Required.

    Reserved for future use.
    """
    http_status = 402
    message = "Payment Required"

    def __init__(self, message=None, **kwargs):
        self.user_id = kwargs.get('user_id')
        self.project_id = kwargs.get('project_id')
        self.owed = kwargs.get('owed')
        super(PaymentRequired, self).__init__(message, **kwargs)


class Forbidden(HTTPClientError):
    """HTTP 403 - Forbidden.

    The request was a valid request, but the server is refusing to respond
    to it.
    """
    http_status = 403
    message = "Forbidden"


class HTTPNotFound(HTTPClientError):
    """HTTP 404 - Not Found.

    The requested resource could not be found but may be available again
    in the future.
    """
    http_status = 404
    message = "Not Found"


class MethodNotAllowed(HTTPClientError):
    """HTTP 405 - Method Not Allowed.

    A request was made of a resource using a request method not supported
    by that resource.
    """
    http_status = 405
    message = "Method Not Allowed"


class NotAcceptable(HTTPClientError):
    """HTTP 406 - Not Acceptable.

    The requested resource is only capable of generating content not
    acceptable according to the Accept headers sent in the request.
    """
    http_status = 406
    message = "Not Acceptable"


class ProxyAuthenticationRequired(HTTPClientError):
    """HTTP 407 - Proxy Authentication Required.

    The client must first authenticate itself with the proxy.
    """
    http_status = 407
    message = "Proxy Authentication Required"


class RequestTimeout(HTTPClientError):
    """HTTP 408 - Request Timeout.

    The server timed out waiting for the request.
    """
    http_status = 408
    message = "Request Timeout"


class Conflict(HTTPClientError):
    """HTTP 409 - Conflict.

    Indicates that the request could not be processed because of conflict
    in the request, such as an edit conflict.
    """
    http_status = 409
    message = "Conflict"


class Gone(HTTPClientError):
    """HTTP 410 - Gone.

    Indicates that the resource requested is no longer available and will
    not be available again.
    """
    http_status = 410
    message = "Gone"


class LengthRequired(HTTPClientError):
    """HTTP 411 - Length Required.

    The request did not specify the length of its content, which is
    required by the requested resource.
    """
    http_status = 411
    message = "Length Required"


class PreconditionFailed(HTTPClientError):
    """HTTP 412 - Precondition Failed.

    The server does not meet one of the preconditions that the requester
    put on the request.
    """
    http_status = 412
    message = "Precondition Failed"


class RequestEntityTooLarge(HTTPClientError):
    """HTTP 413 - Request Entity Too Large.

    The request is larger than the server is willing or able to process.
    """
    http_status = 413
    message = "Request Entity Too Large"

    def __init__(self, *args, **kwargs):
        try:
            self.retry_after = int(kwargs.pop('retry_after'))
        except (KeyError, ValueError):
            self.retry_after = 0

        super(RequestEntityTooLarge, self).__init__(*args, **kwargs)


class RequestUriTooLong(HTTPClientError):
    """HTTP 414 - Request-URI Too Long.

    The URI provided was too long for the server to process.
    """
    http_status = 414
    message = "Request-URI Too Long"


class UnsupportedMediaType(HTTPClientError):
    """HTTP 415 - Unsupported Media Type.

    The request entity has a media type which the server or resource does
    not support.
    """
    http_status = 415
    message = "Unsupported Media Type"


class RequestedRangeNotSatisfiable(HTTPClientError):
    """HTTP 416 - Requested Range Not Satisfiable.

    The client has asked for a portion of the file, but the server cannot
    supply that portion.
    """
    http_status = 416
    message = "Requested Range Not Satisfiable"


class ExpectationFailed(HTTPClientError):
    """HTTP 417 - Expectation Failed.

    The server cannot meet the requirements of the Expect request-header field.
    """
    http_status = 417
    message = "Expectation Failed"


class UnprocessableEntity(HTTPClientError):
    """HTTP 422 - Unprocessable Entity.

    The request was well-formed but was unable to be followed due to semantic
    errors.
    """
    http_status = 422
    message = "Unprocessable Entity"


class InternalServerError(HTTPServerError):
    """HTTP 500 - Internal Server Error.

    A generic error message, given when no more specific message is suitable.
    """
    http_status = 500
    message = "Internal Server Error"


# NotImplemented is a python keyword.
class HTTPNotImplemented(HTTPServerError):
    """HTTP 501 - Not Implemented.

    The server either does not recognize the request method, or it lacks
    the ability to fulfill the request.
    """
    http_status = 501
    message = "Not Implemented"


class BadGateway(HTTPServerError):
    """HTTP 502 - Bad Gateway.

    The server was acting as a gateway or proxy and received an invalid
    response from the upstream server.
    """
    http_status = 502
    message = "Bad Gateway"


class ServiceUnavailable(HTTPServerError):
    """HTTP 503 - Service Unavailable.

    The server is currently unavailable.
    """
    http_status = 503
    message = "Service Unavailable"


class GatewayTimeout(HTTPServerError):
    """HTTP 504 - Gateway Timeout.

    The server was acting as a gateway or proxy and did not receive a timely
    response from the upstream server.
    """
    http_status = 504
    message = "Gateway Timeout"


class HTTPVersionNotSupported(HTTPServerError):
    """HTTP 505 - HTTPVersion Not Supported.

    The server does not support the HTTP protocol version used in the request.
    """
    http_status = 505
    message = "HTTP Version Not Supported"


_code_map = dict(
    (cls.http_status, cls)
    for cls in itertools.chain(HTTPClientError.__subclasses__(),
                               HTTPServerError.__subclasses__()))


def from_response(response, method, url):
    """Returns an instance of :class:`HTTPError` or subclass based on response.

    :param response: instance of `requests.Response` class
    :param method: HTTP method used for request
    :param url: URL used for request
    """
    kwargs = {
        "http_status": response.status_code,
        "response": response,
        "method": method,
        "url": url,
        "request_id": response.headers.get("x-compute-request-id"),
    }
    if "retry-after" in response.headers:
        kwargs["retry_after"] = response.headers["retry-after"]

    content_type = response.headers.get("Content-Type", "")
    if content_type.startswith("application/json"):
        try:
            body = response.json()
        except ValueError:
            pass
        else:
            if hasattr(body, "keys"):
                kwargs["message"] = body.get("message")
                kwargs["details"] = body.get("faultstring")
    elif content_type.startswith("text/"):
        kwargs["details"] = response.text

    if response.status_code == 402:
        kwargs['user_id'] = response.headers.get('user_id')
        kwargs['project_id'] = response.headers.get('project_id')
        kwargs['resource_id'] = response.headers.get('resource_id')

    try:
        cls = _code_map[response.status_code]
    except KeyError:
        if 500 <= response.status_code < 600:
            cls = HTTPServerError
        elif 400 <= response.status_code < 500:
            cls = HTTPClientError
        else:
            cls = HTTPError
    return cls(**kwargs)
