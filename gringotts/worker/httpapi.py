from oslo.config import cfg

from gringotts import exception
from gringotts.openstack.common import log
from gringotts.client import client
from gringotts.openstack.common import timeutils

LOG = log.getLogger(__name__)


TIMESTAMP_TIME_FORMAT = '%Y-%m-%d %H:%M:%S.%f'

cfg.CONF.import_group('service_credentials', 'gringotts.services')


class WorkerAPI(object):

    def __init__(self):
        os_cfg = cfg.CONF.service_credentials
        self.client = client.Client(user_domain_name=os_cfg.user_domain_name,
                                    username=os_cfg.os_username,
                                    password=os_cfg.os_password,
                                    project_domain_name=os_cfg.project_domain_name,
                                    project_name=os_cfg.os_tenant_name,
                                    auth_url=os_cfg.os_auth_url)

    def create_bill(self, ctxt, order_id, action_time=None, remarks=None):
        if isinstance(action_time, basestring):
            action_time = timeutils.parse_strtime(action_time,
                                                  fmt=TIMESTAMP_TIME_FORMAT)
        _body = dict(order_id=order_id,
                     action_time=action_time,
                     remarks=remarks)
        resp, body = self.client.post('/bills', body=_body)
        return body

    def close_bill(self, ctxt, order_id, action_time):
        if isinstance(action_time, basestring):
            action_time = timeutils.parse_strtime(action_time,
                                                  fmt=TIMESTAMP_TIME_FORMAT)
        _body = dict(order_id=order_id,
                     action_time=action_time)
        resp, body = self.client.put('/bills', body=_body)
        return body

    def destory_resource(self, ctxt, order_id):
        pass

    def create_subscription(self, ctxt, order_id, type=None, **kwargs):
        _body = dict(order_id=order_id,
                     type=type,
                     **kwargs)
        resp, body = self.client.post('/subs', body=_body)
        return body

    def change_subscription(self, ctxt, order_id, quantity, change_to):
        _body = dict(order_id=order_id,
                     quantity=quantity,
                     change_to=change_to)
        self.client.put('/subs', body=_body)

    def create_order(self, ctxt, order_id, region_id, unit_price, unit, **kwargs):
        _body = dict(order_id=order_id,
                     region_id=region_id,
                     unit_price=str(unit_price),
                     unit=unit,
                     **kwargs)
        self.client.post('/orders', body=_body)

    def change_order(self, ctxt, order_id, change_to, cron_time=None):
        _body = dict(order_id=order_id,
                     change_to=change_to,
                     cron_time=cron_time)
        self.client.put('/orders', body=_body)

    def get_orders(self, ctxt, status=None, project_id=None, owed=None, region_id=None):
        params = dict(status=status,
                      project_id=project_id,
                      owed=owed,
                      region_id=region_id)
        resp, body = self.client.get('/orders', params=params)
        if body:
            return body['orders']
        return []

    def get_active_orders(self, ctxt, project_id=None, owed=None, region_id=None):
        params = dict(project_id=project_id,
                      owed=owed,
                      region_id=region_id)
        resp, body = self.client.get('/orders/active', params=params)
        if body:
            return body
        return []


    def get_active_order_count(self, ctxt, region_id=None, owed=None):
        params = dict(region_id=region_id,
                      owed=owed)
        resp, body = self.client.get('/orders/count',
                                     params=params)
        return body

    def get_order_by_resource_id(self, ctxt, resource_id):
        params = dict(resource_id=resource_id)
        resp, body = self.client.get('/orders/resource',
                                     params=params)
        return body

    def create_account(self, ctxt, user_id, project_id, balance, consumption, currency,
                       level, **kwargs):
        _body = dict(user_id=user_id,
                     project_id=project_id,
                     balance=balance,
                     consumption=consumption,
                     currency=currency,
                     level=level,
                     **kwargs)
        self.client.post('/accounts', body=_body)

    def get_accounts(self, ctxt):
        resp, body = self.client.get('/accounts')
        return body

    def get_account(self, ctxt, project_id):
        params = dict(project_id=project_id)
        resp, body = self.client.get('/accounts',
                                     params=params)
        return body

    def fix_order(self, ctxt, order_id):
        raise NotImplementedError()
