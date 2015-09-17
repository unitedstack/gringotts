# Copyright 2011 Nebula, Inc.
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
import six
import logging
import requests
from urllib import urlencode

from oslo.config import cfg
from stevedore import driver
from keystoneclient.middleware import auth_token

from gringotts import exception
from gringotts.openstack.common import jsonutils


_logger = logging.getLogger(__name__)


class Client(object):
    """Client for Gringotts"""

    def __init__(self, auth_plugin="token",
                 verify=True, cert=None, timeout=None, *args, **kwargs):
        """Initialize a new Client

        As much as possible the parameters to this class reflect and are passed
        directly to the requests library.

        :param auth_plugin: support two auth plugins: sign and token, default is token
        :param verify: The verification arguments to pass to requests. These
                       are of the same form as requests expects, so True or
                       False to verify (or not) against system certificates or
                       a path to a bundle or CA certs to check against.
                       (optional, defaults to True)
        :param cert: A client certificate to pass to requests. These are of the
                     same form as requests expects. Either a single filename
                     containing both the certificate and key or a tuple
                     containing the path to the certificate then a path to the
                     key. (optional)
        :param float timeout: A timeout to pass to requests. This should be a
                              numerical value indicating some amount
                              (or fraction) of seconds or 0 for no timeout.
                              (optional, defaults to 0)
        """
        self.auth_plugin = driver.DriverManager('gringotts.client_auth_plugin',
                                                auth_plugin,
                                                invoke_on_load=True,
                                                invoke_args=args,
                                                invoke_kwds=kwargs)

        self.auth_plugin = self.auth_plugin.driver
        self.session = requests.Session()
        self.verify = verify
        self.cert = cert
        self.timeout = None

        if timeout is not None:
            self.timeout = float(timeout)

    @staticmethod
    def _decode_body(resp):
        if resp.text:
            try:
                body_resp = jsonutils.loads(resp.text)
            except (ValueError, TypeError):
                body_resp = None
                _logger.debug("Could not decode JSON from body: %s"
                              % resp.text)
        else:
            _logger.debug("No body was returned.")
            body_resp = None

        return body_resp

    def request(self, url, method, **kwargs):
        """Send an http request with the specified characteristics.

        Wrapper around requests.request to handle tasks such as
        setting headers, JSON encoding/decoding, and error handling.
        """
        # url
        url = self.auth_plugin.get_endpoint() + url

        # headers
        headers = kwargs.setdefault('headers', dict())
        headers['User-Agent'] = "python-gringclient"
 
        # others
        if self.cert:
            kwargs.setdefault('cert', self.cert)
        if self.timeout is not None:
            kwargs.setdefault('timeout', self.timeout)
        kwargs.setdefault('verify', self.verify)

        # body
        try:
            kwargs['data'] = jsonutils.dumps(kwargs.pop('body'))
            headers['Content-Type'] = 'application/json'
        except KeyError:
            pass

        # params
        try:
            kwargs['params'] = self.auth_plugin.filter_params(kwargs['params'])
        except KeyError:
            pass

        # NOTE(suo): It is because signauture auth method will sign the
        # body, so we should put headers after body
        headers.update(self.auth_plugin.get_auth_headers(**kwargs))

        # build curl log
        string_parts = ['curl -i']

        if method:
            string_parts.extend([' -X ', method])

        query_string = "?%s" % urlencode(kwargs.get('params')) if kwargs.get('params') else ""
        string_parts.extend([' ', url + query_string])

        if headers:
            for header in six.iteritems(headers):
                string_parts.append(' -H "%s: %s"' % header)

        data = kwargs.get('data')
        if data:
            string_parts.append(' -d \'%s\'' % data)

        _logger.debug('REQ: %s', ''.join(string_parts))

        # send request
        resp = self._send_request(url, method, **kwargs)

        if resp.status_code >= 400:
            _logger.debug('Request returned failure status: %s',
                          resp.status_code)
            raise exception.from_response(resp, method, url)

        return resp, self._decode_body(resp)

    def _send_request(self, url, method, **kwargs):
        try:
            resp = self.session.request(method, url, **kwargs)
        except requests.exceptions.SSLError:
            msg = 'SSL exception connecting to %s' % url
            raise exception.SSLError(msg)
        except requests.exceptions.Timeout:
            msg = 'Request to %s timed out' % url
            raise exception.Timeout(msg)
        except requests.exceptions.ConnectionError:
            msg = 'Unable to establish connection to %s' % url
            raise exception.ConnectionError(message=msg)

        _logger.debug('RESP: [%s] %s\nRESP BODY: %s\n',
                      resp.status_code, resp.headers, resp.text)

        # NOTE(jamielennox): The requests lib will handle the majority of
        # redirections. Where it fails is when POSTs are redirected which
        # is apparently something handled differently by each browser which
        # requests forces us to do the most compliant way (which we don't want)
        # see: https://en.wikipedia.org/wiki/Post/Redirect/Get
        # Nova and other direct users don't do this. Is it still relevant?
        if resp.status_code in (301, 302, 305):
            # Redirected. Reissue the request to the new location.
            return self._send_request(resp.headers['location'],
                                      method, **kwargs)

        return resp

    def get(self, url, **kwargs):
        return self.request(url, 'GET', **kwargs)

    def head(self, url, **kwargs):
        return self.request(url, 'HEAD', **kwargs)

    def post(self, url, **kwargs):
        return self.request(url, 'POST', **kwargs)

    def put(self, url, **kwargs):
        return self.request(url, 'PUT', **kwargs)

    def patch(self, url, **kwargs):
        return self.request(url, 'PATCH', **kwargs)

    def delete(self, url, **kwargs):
        return self.request(url, 'DELETE', **kwargs)


def get_client():
    """Only can be used after CONF is initialized
    """
    from gringotts.services import keystone
    from gringotts.client.v2 import client
    ks_cfg = cfg.CONF.keystone_authtoken
    auth_url = keystone.get_auth_url()
    try:
        c = client.Client(username=ks_cfg.admin_user,
                          password=ks_cfg.admin_password,
                          project_name=ks_cfg.admin_tenant_name,
                          auth_url=auth_url)
        return c
    except (exception.Unauthorized, exception.AuthorizationFailure):
        self._logger.exception("Billing Authorization Failed - rejecting request")
        raise
    except Exception as e:
        msg = 'Fail to initialize the billing client, for the reason: %s' % e
        self._logger.exception(msg)
        raise
