"""
The simple version of keystone auth method, verify keystone
v3 token only.

Mainly do two things:
    1. get token
    2. Re-get token if the token is expired
"""
import datetime
import requests

from gringotts import utils
from gringotts import exception
from gringotts.client.auth import BaseAuthPlugin
from gringotts.openstack.common import jsonutils
from gringotts.openstack.common import timeutils


STALE_TOKEN_DURATION = 30


def will_expire_soon(expires, stale_duration=None):
    """Determines if expiration is about to occur.

    :return: boolean : true if expiration is within the given duration

    """
    stale_duration = (STALE_TOKEN_DURATION if stale_duration is None
                      else int(stale_duration))
    norm_expires = timeutils.normalize_time(expires)
    soon = (timeutils.utcnow() + datetime.timedelta(seconds=stale_duration))
    return norm_expires < soon


class TokenAuthPlugin(BaseAuthPlugin):
    """Get auth token and endpoint from keystone
    """

    def __init__(self,
                 user_id=None,
                 username=None,
                 user_domain_id=None,
                 user_domain_name=None,
                 project_id=None,
                 project_name=None,
                 project_domain_id=None,
                 project_domain_name=None,
                 password=None,
                 auth_url=None,
                 **kwargs):
        """Support two kinds of token auth method:
        1. username/password, this will request keystone for token
        2. token/endpoint, this will use existing token and endpoint,
           there is no need to authenticate again.
        """
        self._management_url = None
        self._auth_token = None
        self._expires_at = None

        self.user_id = user_id
        self.username = username
        if user_domain_id:
            self.user_domain_id = user_domain_id
        elif not (user_id or user_domain_name):
            self.user_domain_id = 'default'
        else:
            self.user_domain_id = None
        self.user_domain_name = user_domain_name
        self.project_id = project_id
        self.project_name = project_name
        if project_domain_id:
            self.project_domain_id = project_domain_id
        elif not (project_id or project_domain_name):
            self.project_domain_id = 'default'
        else:
            self.project_domain_id = None
        self.project_domain_name = project_domain_name
        self.password = password
        self.auth_url = auth_url

        self.stale_duration = kwargs.get('stale_duration')
        self.version = kwargs.get('version')
        self.service_type = kwargs.get('service_type') or 'billing'

        if self.management_url is None:
            self.authenticate()

    @property
    def auth_token(self):
        if will_expire_soon(self._expires_at, self.stale_duration):
            self.authenticate()
        return self._auth_token

    @auth_token.setter
    def auth_token(self, value):
        self._auth_token = value

    @property
    def management_url(self):
        return self._management_url

    def get_auth_headers(self, **kwargs):
        if self.auth_token is None:
            raise exception.NotAuthorized(
                'Current authorization does not have a token')
        return {'X-Auth-Token': self.auth_token}

    def get_endpoint(self):
        if self.management_url is None:
            raise exception.NotAuthorized(
                'Current authorization does not have a known billing management url')
        return self.management_url

    @staticmethod
    def _decode_body(resp):
        if resp.text:
            try:
                body_resp = jsonutils.loads(resp.text)
            except (ValueError, TypeError):
                body_resp = None
        else:
            body_resp = None

        return body_resp

    def authenticate(self):
        """Authenticate user."""
        kwargs = {
            'auth_url': self.auth_url,
            'user_id': self.user_id,
            'username': self.username,
            'user_domain_id': self.user_domain_id,
            'user_domain_name': self.user_domain_name,
            'project_id': self.project_id,
            'project_name': self.project_name,
            'project_domain_id': self.project_domain_id,
            'project_domain_name': self.project_domain_name,
            'password': self.password,
        }
        resp, body = self.get_raw_token_from_identity_service(**kwargs)

        self._expires_at = timeutils.parse_isotime(body['token']['expires_at'])
        self.auth_token = resp.headers['X-Subject-Token']
        self._management_url = self._get_endpoint(body['token']['catalog'],
                                                  version=self.version,
                                                  service_type=self.service_type)
        return True

    def _get_endpoint(self, catalog, version=None, service_type=None):
        for item in catalog:
            if item['type'] != self.service_type:
                continue
            for endpoint in item['endpoints']:
                if endpoint['interface'] == 'admin':
                    return utils.version_api(endpoint['url'],
                                             version=version)

    def get_raw_token_from_identity_service(self,
                                            user_id=None,
                                            username=None,
                                            user_domain_id=None,
                                            user_domain_name=None,
                                            project_id=None,
                                            project_name=None,
                                            project_domain_id=None,
                                            project_domain_name=None,
                                            password=None,
                                            auth_url=None):
        """Authenticate against the Identity API and get a token.
        """
        try:
            return self._do_auth(
                auth_url=auth_url,
                user_id=user_id,
                username=username,
                user_domain_id=user_domain_id,
                user_domain_name=user_domain_name,
                project_id=project_id,
                project_name=project_name,
                project_domain_id=project_domain_id,
                project_domain_name=project_domain_name,
                password=password)
        except (exception.AuthorizationFailure, exception.Unauthorized):
            _logger.debug('Authorization failed.')
            raise
        except Exception as e:
            raise exception.AuthorizationFailure('Authorization failed: %s' % e)

    def _do_auth(self,
                 auth_url=None,
                 user_id=None,
                 username=None,
                 user_domain_id=None,
                 user_domain_name=None,
                 project_id=None,
                 project_name=None,
                 project_domain_id=None,
                 project_domain_name=None,
                 password=None):
        # headers
        headers = {'Content-Type': 'application/json'}

        if auth_url is None:
            raise ValueError("Cannot authenticate without a valid auth_url")

        # body
        url = auth_url + "/auth/tokens"
        body = {'auth': {'identity': {}}}
        ident = body['auth']['identity']

        if password:
            ident['methods'] = ['password']
            ident['password'] = {}
            ident['password']['user'] = {}
            user = ident['password']['user']
            user['password'] = password

            if user_id:
                user['id'] = user_id
            elif username:
                user['name'] = username
                if user_domain_id or user_domain_name:
                    user['domain'] = {}
                if user_domain_id:
                    user['domain']['id'] = user_domain_id
                elif user_domain_name:
                    user['domain']['name'] = user_domain_name

        if project_id or project_name:
            body['auth']['scope'] = {}
            scope = body['auth']['scope']
            scope['project'] = {}

            if project_id:
                scope['project']['id'] = project_id
            elif project_name:
                scope['project']['name'] = project_name

                if project_domain_id or project_domain_name:
                    scope['project']['domain'] = {}
                if project_domain_id:
                    scope['project']['domain']['id'] = project_domain_id
                elif project_domain_name:
                    scope['project']['domain']['name'] = project_domain_name

        resp = requests.post(url,
                             data=jsonutils.dumps(body),
                             headers=headers)
        return resp, self._decode_body(resp)
