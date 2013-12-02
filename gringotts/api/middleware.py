# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
#
# Author: Doug Hellmann <doug.hellmann@dreamhost.com>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
"""
Middleware to replace the plain text message body of an error
response with one formatted so the client can parse it.

Based on pecan.middleware.errordocument
"""

import json
import webob
import webob.dec

from gringotts.openstack.common import log


LOG = log.getLogger(__name__)


class Fault(object):

    def __init__(self, error):
        self.error = error

    @webob.dec.wsgify
    def __call__(self, req):
        error = {
            'msg': {
                'en-US': getattr(self.error, 'explanation', 'UNKONWN ERROR')
            }
        }
        response = webob.Response()
        response.status_int = getattr(self.error, 'code', 500)
        response.content_type = 'application/json'
        response.unicode_body = unicode(json.dumps(error))
        return response


class FaultWrapperMiddleware(object):

    def __init__(self, app):
        self.app = app

    @webob.dec.wsgify
    def __call__(self, req):
        try:
            resp = req.get_response(self.app)
            ex = req.environ.get('pecan.original_exception', None)
            if ex:
                raise ex
            return resp
        except Exception as e:
            return Fault(e)
