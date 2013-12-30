# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack Foundation.
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

"""
Simple class that stores security context information in the web request.

Projects should subclass this class if they wish to enhance the request
context or provide additional information in their specific WSGI pipeline.
"""

import itertools

from gringotts import exception
from gringotts.openstack.common import uuidutils


def generate_request_id():
    return 'req-%s' % uuidutils.generate_uuid()


class RequestContext(object):

    """Helper class to represent useful information about a request context.

    Stores information about the security context under which the user
    accesses the system, as well as additional request information.
    """

    def __init__(self, auth_token=None, user_id=None, project_id=None,
                 is_admin=False, request_id=None):
        self.auth_token = auth_token
        self.user_id = user_id
        self.project_id = project_id
        self.user = user_id
        self.tenant = project_id
        self.is_admin = is_admin
        if not request_id:
            request_id = generate_request_id()
        self.request_id = request_id

    def to_dict(self):
        return {'user_id': self.user_id,
                'project_id': self.project_id,
                'user': self.user,
                'tenant': self.tenant,
                'is_admin': self.is_admin,
                'auth_token': self.auth_token,
                'request_id': self.request_id}


def get_admin_context(show_deleted=False):
    context = RequestContext(is_admin=True)
    return context


def get_context_from_function_and_args(function, args, kwargs):
    """Find an arg of type RequestContext and return it.

       This is useful in a couple of decorators where we don't
       know much about the function we're wrapping.
    """

    for arg in itertools.chain(kwargs.values(), args):
        if isinstance(arg, RequestContext):
            return arg

    return None


def is_user_context(context):
    """Indicates if the request context is a normal user."""
    if not context:
        return False
    if context.is_admin:
        return False
    if not context.user_id or not context.project_id:
        return False
    return True


def require_context(ctxt):
    if not ctxt.is_admin and not is_user_context(ctxt):
        raise exception.NotAuthorized()


def require_admin_context(ctxt):
    if not ctxt.is_admin:
        raise exception.NotAuthorized()
