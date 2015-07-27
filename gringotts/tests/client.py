
import six
from stevedore import driver

from gringotts.client import client
from gringotts.openstack.common import jsonutils
from gringotts.openstack.common import log as logging

LOG = logging.getLogger(__name__)


class Client(client.Client):
    """HTTP client used in unit tests

    This client will send HTTP request to WebTest app, so all
    the requests will really go through gringotts API and operate
    on the database.
    """

    def __init__(self, app, version, auth_plugin="token", verify=True,
                 cert=None, timeout=None, *args, **kwargs):
        self.app = app
        self.version = '/%s' % version

        self.auth_plugin = driver.DriverManager(
            'gringotts.client_auth_plugin', auth_plugin,
            invoke_on_load=True, invoke_args=args, invoke_kwds=kwargs
        )
        self.auth_plugin = self.auth_plugin.driver

        self.session = None
        self.verify = verify
        self.cert = cert
        self.timeout = float(timeout) if timeout else None

    def request(self, path, method, **kwargs):
        path = self.version + path

        headers = kwargs.pop('headers', dict())
        headers['User-Agent'] = 'python-gringclient'

        # TODO(liuchenhong): not support SSL request right now
        try:
            kwargs.pop('cert')
        except (KeyError):
            pass

        try:
            kwargs.pop('verify')
        except (KeyError):
            pass

        # request params
        try:
            params = kwargs.pop('params')
        except (KeyError):
            params = None

        if params:
            query_vars = [
                '%s=%s' % (k, v) for k, v in six.iteritems(params)
            ]
            path += '?%s' % ('&'.join(query_vars))

        # request body
        try:
            body = kwargs.pop('body')
            if not isinstance(body, str):
                body = jsonutils.dumps(body)
            json_body = body
            headers['Content-Type'] = 'application/json'
        except (KeyError):
            json_body = None

        # authenticate headers
        headers.update(self.auth_plugin.get_auth_headers(
            params=params, body=json_body))
        LOG.debug('HTTP request headers: %s', headers)
        LOG.debug('%s %s', method, path)

        resp = self.app.request(path, headers=headers, body=json_body,
                                method=method, **kwargs)

        # The first argument returned here is not a request.Response
        # object, but a webob.response.Response. if caller need to get
        # anything from it, it should be mocked.
        return resp, self._decode_body(resp)

    @staticmethod
    def _decode_body(resp):
        try:
            json_body = resp.json_body
        except (Exception):
            json_body = None

        return json_body


class MasterApi(object):
    """Master API used in unit test.

    Original MasterAPI class used rpc to call a method of master
    service. We need to replace rpc method with direct method.
    """

    def __init__(self, service):
        self.service = service

    def get_cronjob_count(self, *args, **kwargs):
        return self.service.get_cronjob_count(*args, **kwargs)

    def get_datejob_count(self, *args, **kwargs):
        return self.service.get_datejob_count(*args, **kwargs)

    def get_datejob_count_30_days(self, *args, **kwargs):
        return self.service.get_datejob_count_30_days(*args, **kwargs)

    def resource_created(self, *args, **kwargs):
        return self.service.resource_created(*args, **kwargs)

    def resource_created_again(self, *args, **kwargs):
        return self.service.resource_created_again(*args, **kwargs)

    def resource_started(self, *args, **kwargs):
        return self.service.resource_started(*args, **kwargs)

    def resource_stopped(self, *args, **kwargs):
        return self.service.resource_stopped(*args, **kwargs)

    def resource_deleted(self, *args, **kwargs):
        return self.service.resource_deleted(*args, **kwargs)

    def resource_changed(self, *args, **kwargs):
        return self.service.resource_changed(*args, **kwargs)

    def resource_resized(self, *args, **kwargs):
        return self.service.resource_resized(*args, **kwargs)

    def instance_stopped(self, *args, **kwargs):
        return self.service.instance_stopped(*args, **kwargs)

    def instance_resized(self, *args, **kwargs):
        return self.service.instance_resized(*args, **kwargs)
