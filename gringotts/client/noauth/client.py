import logging

from gringotts.client import client
from gringotts import exception
from gringotts.openstack.common import timeutils
from gringotts.openstack.common import uuidutils
from gringotts import utils as gringutils


LOG = logging.getLogger(__name__)
TIMESTAMP_TIME_FORMAT = '%Y-%m-%d %H:%M:%S.%f'

quantize_decimal = gringutils._quantize_decimal


class Client(object):
    """Client for gringotts noauth API
    """
    def __init__(self, auth_plugin="noauth",
                 verify=True, cert=None, timeout=None, *args, **kwargs):
        self.client = client.Client(auth_plugin=auth_plugin,
                                    verify=verify,
                                    cert=cert,
                                    timeout=timeout,
                                    *args, **kwargs)

    def create_account(self, user_id, domain_id,
                       balance, consumption, level, **kwargs):
        _body = dict(user_id=user_id,
                     domain_id=domain_id,
                     balance=balance,
                     consumption=consumption,
                     level=level,
                     **kwargs)
        self.client.post('/accounts', body=_body)

    def create_project(self, project_id, domain_id, consumption, user_id=None):
        _body = dict(user_id=user_id,
                     project_id=project_id,
                     domain_id=domain_id,
                     consumption=consumption)
        self.client.post('/projects', body=_body)

    def delete_resources(self, project_id, region_name=None):
        params = dict(project_id=project_id,
                      region_name=region_name)
        self.client.delete('/resources', params=params)

    def change_billing_owner(self, user_id, project_id):
        _body = dict(user_id=user_id)
        self.client.put('/projects/%s/billing_owner' % project_id, body=_body)

    def get_project(self, project_id):
        resp, body = self.client.get('/projects/%s' % project_id)
        return body
