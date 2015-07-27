
import mock
from oslo_config import cfg
from oslotest import mockpatch
import six

from gringotts.client import client
from gringotts.master import rpcapi as master_rpcapi
from gringotts.master import service as master_service
from gringotts.openstack.common import log as logging
from gringotts.tests import client as test_client
from gringotts.tests import core as tests
from gringotts.tests import utils as test_utils
from gringotts.waiter import service as waiter_service

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class ServiceTestCase(tests.TestCase):

    def setUp(self):
        super(ServiceTestCase, self).setUp()

        # Load test http client which will forward http requests
        # to test app instead of real service. This is used to
        # replace http client used in worker HTTPAPI.
        self.client = test_client.Client(self.app, 'v2')
        self.clean_attr('client')
        MockedClient = mock.MagicMock(name='MockedClient',
                                      return_value=self.client)
        self.useFixture(mockpatch.PatchObject(client, 'Client',
                                              MockedClient))

    def load_sample_data(self):
        super(ServiceTestCase, self).load_sample_data()


class MasterServiceTestCase(ServiceTestCase):

    def setUp(self):
        super(MasterServiceTestCase, self).setUp()

        self.service = master_service.MasterService()


class WaiterServiceTestCase(ServiceTestCase,
                            test_utils.PricingTestMixin):

    def setUp(self):
        super(WaiterServiceTestCase, self).setUp()

        self.service = waiter_service.WaiterService(CONF.host,
                                                    'gringotts.waiter')
        self.master_service = master_service.MasterService()

        # Load test master rpcapi which will directly call api of
        # master service. This is used to replace rpcapi used by
        # waiter plugins
        self.master_api = test_client.MasterApi(self.master_service)
        self.clean_attr('master_api')
        MockedRpcApi = mock.MagicMock(name='MockedRpcApi',
                                      return_value=self.master_api)
        self.useFixture(mockpatch.PatchObject(
            master_rpcapi, 'MasterAPI', MockedRpcApi))

        http_headers = self.build_admin_http_headers()
        mocked_get_auth_headers = mock.MagicMock(return_value=http_headers)
        self.useFixture(mockpatch.PatchObject(
            self.client.auth_plugin, 'get_auth_headers',
            mocked_get_auth_headers
        ))

    def build_notification_message(self, user_id, event_type, payload,
                                   publisher_id='gringotts.test',
                                   message_id=None, priority='INFO',
                                   timestamp=None, **kwargs):

        if message_id is None:
            message_id = self.new_uuid4()
        if timestamp is None:
            timestamp = self.datetime_to_str(self.utcnow())
        else:
            timestamp = self.datetime_to_str(timestamp)

        message = {
            '_context_user_id': user_id,
            '_context_project_name': kwargs.get('project_name',
                                                self.new_project_id()),
            'event_type': event_type,
            'message_id': message_id,
            'payload': payload,
            'publisher_id': publisher_id,
            'priority': priority,
            'timestamp': timestamp,
        }
        return message

    def build_floatingip_payload(self, floating_ip_address, rate_limit,
                                 project_id, **kwargs):

        floatingip = {
            'floating_ip_address': floating_ip_address,
            'rate_limit': rate_limit,  # unit: Kbps/s
            'tenant_id': project_id,

            # auto generated data
            'created_at': kwargs.get(
                'created_at', self.datetime_to_isotime_str(self.utcnow())),
            'id': kwargs.get('id', self.new_resource_id()),
            'fixed_ip_address': kwargs.get('fixed_ip_address', None),
            'floating_network_id': kwargs.get(
                'floating_network_id', self.new_resource_id()),
            'floating_subnet_id': kwargs.get(
                'floating_subnet_id', self.new_resource_id()),
            'port_id': kwargs.get('port_id', None),
            'router_id': kwargs.get('router_id', None),
            'status': kwargs.get('status', 'UP'),
            'uos:name': kwargs.get('uos_name', self.new_uuid()),
            'uos:registerno': kwargs.get('uos_registerno', ''),
            'uos.service_provider': kwargs.get('uos_service_provider', ''),
        }

        return {'floatingip': floatingip}

    def build_floatingipset_payload(self, fipset, rate_limit,
                                    project_id, **kwargs):

        floatingipset = {
            'floatingipset_address': fipset,
            'uos:service_provider': list(six.iterkeys(fipset)),
            'rate_limit': rate_limit,
            'tenant_id': project_id,

            # auto generated data
            'created_at': kwargs.get(
                'created_at', self.datetime_to_isotime_str(self.utcnow())),
            'id': kwargs.get('id', self.new_resource_id()),
            'uos:name': kwargs.get('uos_name', self.new_uuid()),
        }

        return {'floatingipset': floatingipset}
