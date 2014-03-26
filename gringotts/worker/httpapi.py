from oslo.config import cfg

from gringotts.openstack.common import log
from gringotts.client import client
from gringotts.openstack.common import timeutils

LOG = log.getLogger(__name__)


OPTS = [
    cfg.StrOpt('username',
               default='admin',
               help='admin username'),
    cfg.StrOpt('password',
               default='admin',
               help='admin password'),
    cfg.StrOpt('project_name',
               default='admin',
               help='admin project'),
    cfg.StrOpt('user_domain_name',
               default='Default',
               help='user domain name'),
    cfg.StrOpt('project_domain_name',
               default='Default',
               help='project domain name'),
    cfg.StrOpt('auth_url',
               default='http://localhost:35357/v3'),
]

cfg.CONF.register_opts(OPTS, group="worker")
TIMESTAMP_TIME_FORMAT = '%Y-%m-%d %H:%M:%S.%f'


class WorkerAPI(object):

    def __init__(self):
        ks_cfg = cfg.CONF.worker
        self.client = client.Client(user_domain_name=ks_cfg.user_domain_name,
                                    username=ks_cfg.username,
                                    password=ks_cfg.password,
                                    project_domain_name=ks_cfg.project_domain_name,
                                    project_name=ks_cfg.project_name,
                                    auth_url=ks_cfg.auth_url)

    def create_bill(self, ctxt, order_id, action_time=None, remarks=None):
        if isinstance(action_time, basestring):
            action_time = timeutils.parse_strtime(action_time,
                                                  fmt=TIMESTAMP_TIME_FORMAT)
        body = dict(order_id=order_id,
                    action_time=action_time,
                    remarks=remarks)
        self.client.post('/bills', body=body)

    def close_bill(self, ctxt, order_id, action_time):
        if isinstance(action_time, basestring):
            action_time = timeutils.parse_strtime(action_time,
                                                  fmt=TIMESTAMP_TIME_FORMAT)
        body = dict(order_id=order_id,
                    action_time=action_time)
        self.client.put('/bills', body=body)

    def destory_resource(self, ctxt, order_id):
        pass

    def create_subscription(self, ctxt, order_id, type=None, **kwargs):
        body = dict(order_id=order_id,
                    type=type,
                    **kwargs)
        resp, body = self.client.post('/subs', body=body)
        return body

    def change_subscription(self, ctxt, order_id, quantity, change_to):
        body = dict(order_id=order_id,
                    quantity=quantity,
                    change_to=change_to)
        self.client.put('/subs', body=body)

    def create_order(self, ctxt, order_id, region_id, unit_price, unit, **kwargs):
        body = dict(order_id=order_id,
                    region_id=region_id,
                    unit_price=str(unit_price),
                    unit=unit,
                    **kwargs)
        self.client.post('/orders', body=body)

    def change_order(self, ctxt, order_id, change_to):
        body = dict(order_id=order_id,
                    change_to=change_to)
        self.client.put('/orders', body=body)

    def get_orders(self, ctxt, status=None):
        params = dict(status=status)
        resp, body = self.client.get('/orders', params=params)
        if body:
            return body['orders']
        return []

    def get_order_by_resource_id(self, ctxt, resource_id):
        params = dict(resource_id=resource_id)
        resp, body = self.client.get('/orders/resource',
                                     params=params)
        return body
