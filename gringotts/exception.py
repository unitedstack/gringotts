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

import functools

from oslo.config import cfg
import six

from gringotts.openstack.common import excutils
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
    message = _("The user %(user_id)s balance is not sufficient")
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


class InvalidUUID(Invalid):
    message = _("Expected a uuid but received %(uuid)s.")


class InvalidIdentity(Invalid):
    message = _("Expected an uuid or int but received %(identity)s.")


class ImageUnacceptable(GringottsException):
    message = _("Image %(image_id)s is unacceptable: %(reason)s")


class InstanceStateError(GringottsException):
    message = _("The state of the instance %(instance_id)s is not active")


# Cannot be templated as the error syntax varies.
# msg needs to be constructed when raised.
class InvalidParameterValue(Invalid):
    message = _("%(err)s")


class NotFound(GringottsException):
    message = _("Resource could not be found.")
    code = 404


class ProductIdNotFound(NotFound):
    message = _("Product %(product_id)s could not be found")


class ProductNameNotFound(NotFound):
    message = _("Product %(product_name)s could not be found")


class LatestBillNotFound(NotFound):
    message = _("Can't find latest bill for subscription: %s(subscription_id)s")


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


class Forbidden(GringottsException):
    message = _("Requested OpenStack Images API is forbidden")


class BadRequest(GringottsException):
    pass


class HTTPException(GringottsException):
    message = _("Requested version of OpenStack Images API is not available.")


class InvalidEndpoint(GringottsException):
    message = _("The provided endpoint is invalid")


class CommunicationError(GringottsException):
    message = _("Unable to communicate with the server.")


class HTTPForbidden(Forbidden):
    pass


class Unauthorized(GringottsException):
    pass


class HTTPNotFound(NotFound):
    pass


class ConfigNotFound(GringottsException):
    message = _("Could not find config at %(path)s")
