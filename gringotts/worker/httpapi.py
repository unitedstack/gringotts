from oslo.config import cfg

from gringotts import exception
from gringotts.openstack.common import log
from gringotts.client import client
from gringotts.openstack.common import timeutils
from gringotts.openstack.common import uuidutils

LOG = log.getLogger(__name__)


TIMESTAMP_TIME_FORMAT = '%Y-%m-%d %H:%M:%S.%f'

cfg.CONF.import_group('service_credentials', 'gringotts.service')


class WorkerAPI(object):

    def __init__(self, external_client=None):
        # external client
        self.external_client = external_client

        # internal client
        os_cfg = cfg.CONF.service_credentials
        self.client = client.Client(user_domain_name=os_cfg.user_domain_name,
                                    username=os_cfg.os_username,
                                    password=os_cfg.os_password,
                                    project_domain_name=os_cfg.project_domain_name,
                                    project_name=os_cfg.os_tenant_name,
                                    auth_url=os_cfg.os_auth_url)

    def create_bill(self, ctxt, order_id, action_time=None, remarks=None, end_time=None):
        if isinstance(action_time, basestring):
            action_time = timeutils.parse_strtime(action_time,
                                                  fmt=TIMESTAMP_TIME_FORMAT)
        if isinstance(end_time, basestring):
            end_time = timeutils.parse_strtime(end_time,
                                               fmt=TIMESTAMP_TIME_FORMAT)
        _body = dict(order_id=order_id,
                     action_time=action_time,
                     remarks=remarks,
                     end_time=end_time)
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

    def get_product(self, ctxt, product_name, service, region_id):
        params = dict(name=product_name,
                      service=service,
                      region_id=region_id)
        resp, body = self.client.get('/products', params=params)
        if body:
            return body[0]
        return None

    def create_subscription(self, ctxt, order_id, type=None, **kwargs):
        _body = dict(order_id=order_id,
                     type=type,
                     **kwargs)
        resp, body = self.client.post('/subs', body=_body)
        return body

    def get_subscriptions(self, ctxt, order_id=None, type=None):
        params = dict(type=type,
                      order_id=order_id)
        resp, body = self.client.get('/subs', params=params)
        if body:
            return body
        return None

    def change_subscription(self, ctxt, order_id, quantity, change_to):
        _body = dict(order_id=order_id,
                     quantity=quantity,
                     change_to=change_to)
        self.client.put('/subs', body=_body)

    def change_flavor_subscription(self, ctxt, order_id, new_flavor, old_flavor,
                                   service, region_id, change_to):
        _body = dict(order_id=order_id,
                     new_flavor=new_flavor,
                     old_flavor=old_flavor,
                     service=service,
                     region_id=region_id,
                     change_to=change_to)
        self.client.put('/subs', body=_body)

    def create_order(self, ctxt, order_id, region_id, unit_price, unit, **kwargs):
        _body = dict(order_id=order_id,
                     region_id=region_id,
                     unit_price=str(unit_price),
                     unit=unit,
                     **kwargs)
        self.client.post('/orders', body=_body)

    def change_order(self, ctxt, order_id, change_to, cron_time=None,
                     change_order_status=True, first_change_to=None):
        _body = dict(order_id=order_id,
                     change_to=change_to,
                     cron_time=cron_time,
                     change_order_status=change_order_status,
                     first_change_to=first_change_to)
        self.client.put('/orders', body=_body)

    def get_orders(self, ctxt, status=None, project_id=None, owed=None, region_id=None, type=None):
        params = dict(status=status,
                      type=type,
                      project_id=project_id,
                      owed=owed,
                      region_id=region_id)
        resp, body = self.client.get('/orders', params=params)
        if body:
            return body['orders']
        return []

    def get_active_orders(self, ctxt, user_id=None, project_id=None, owed=None,
                          charged=None, region_id=None):
        params = dict(user_id=user_id,
                      project_id=project_id,
                      owed=owed,
                      charged=charged,
                      region_id=region_id)
        resp, body = self.client.get('/orders/active', params=params)
        if body:
            return body
        return []


    def get_active_order_count(self, ctxt, region_id=None, owed=None, type=None):
        params = dict(region_id=region_id,
                      owed=owed,
                      type=type)
        resp, body = self.client.get('/orders/count',
                                     params=params)
        return body

    def get_stopped_order_count(self, ctxt, region_id=None, owed=None, type=None):
        params = dict(region_id=region_id,
                      owed=owed,
                      type=type)
        resp, body = self.client.get('/orders/stopped',
                                     params=params)
        return body

    def get_order_by_resource_id(self, ctxt, resource_id):
        params = dict(resource_id=resource_id)
        resp, body = self.client.get('/orders/resource',
                                     params=params)
        return body

    def get_order(self, ctxt, order_id):
        resp, body = self.client.get('/orders/%s/order' % order_id)
        return body

    def reset_charged_orders(self, ctxt, order_ids):
        _body = dict(order_ids=order_ids)
        self.client.put('/orders/reset', body=_body)

    def create_account(self, ctxt, user_id, domain_id, balance,
                       consumption, level, **kwargs):
        _body = dict(user_id=user_id,
                     domain_id=domain_id,
                     balance=balance,
                     consumption=consumption,
                     level=level,
                     **kwargs)
        self.client.post('/accounts', body=_body)

    def get_accounts(self, ctxt, owed=None):
        params = dict(owed=owed)
        resp, body = self.client.get('/accounts', params=params)
        return body['accounts']

    def get_account(self, ctxt, user_id):
        resp, body = self.client.get('/accounts/%s' % user_id)
        return body

    def charge_account(self, ctxt, user_id, value, type, come_from):
        _body = dict(value=value,
                     type=type,
                     come_from=come_from)
        self.client.put('/accounts/%s' % user_id, body=_body)

    def create_project(self, ctxt, user_id, project_id, domain_id, consumption):
        _body = dict(user_id=user_id,
                     project_id=project_id,
                     domain_id=domain_id,
                     consumption=consumption)
        self.client.post('/projects', body=_body)

    def get_projects(self, ctxt, user_id=None, type=None):
        params = dict(user_id=user_id,
                      type=type)
        resp, body = self.client.get('/projects', params=params)
        return body

    def delete_resources(self, ctxt, project_id, region_name=None):
        params = dict(project_id=project_id,
                      region_name=region_name)
        self.client.delete('/resources', params=params)

    def get_resources(self, ctxt, project_id, region_name=None):
        params = dict(project_id=project_id,
                      region_name=region_name)
        resp, body = self.client.get('/resources', params=params)
        return body

    def change_billing_owner(self, ctxt, project_id, user_id):
        _body = dict(user_id=user_id)
        self.client.put('/projects/%s/billing_owner' % project_id, body=_body)

    def fix_order(self, ctxt, order_id):
        raise NotImplementedError()

    def create_deduct(self, ctxt, user_id, money, type="1", remark=None, req_id=None, **kwargs):
        """Only create deduct record in database, not deduct account
        """
        req_id = req_id if req_id else uuidutils.generate_uuid()

        _body = dict(reqId=req_id,
                     accountNum=user_id,
                     money=money,
                     type=type,
                     remark=remark,
                     extData=kwargs,
                     deduct=False)

        failed = False

        try:
            __, body = self.client.put('/pay', body=_body)
            if body['code'] != "0":
                failed = True
        except Exception:
            failed = True

        if failed:
            LOG.warn("Fail to backup the deduct: user_id: %s, money: %s" % (user_id, money))

    def deduct_external_account(self, ctxt, user_id, money, type="1", remark=None, req_id=None, **kwargs):
        """Deduct the account from external billing system

        if failed, will check the account was deducted successfully:
            if successfull:
                will return gracefully
            if failed:
                will deduct the account again
                if successfull:
                    return gracefully
                elif failed:
                    raise Exception
        elif successfull:
            will return gracefully
        """
        if not self.external_client:
            return

        req_id = req_id if req_id else uuidutils.generate_uuid()

        _body = dict(reqId=req_id,
                     accountNum=user_id,
                     money=money,
                     type=type,
                     remark=remark,
                     extData=kwargs)

        failed = False
        retry = False

        # deduct first
        try:
            __, body = self.external_client.put('/pay', body=_body)
            if body['code'] != "0":
                failed = True
        except Exception:
            failed = True

        # check
        # if checking itself is failed, then we think the deduction is failed
        if failed:
            params = dict(reqId=req_id)
            try:
                __, body = self.external_client.get('/checkReq', params=params)
                if body['code'] != "0":
                    raise Exception
            except Exception:
                msg = "Deduct external account(%s) failed, deduct money(%s), req_id(%s)" % \
                        (user_id, money, req_id)
                LOG.exception(msg)
                raise exception.DeductError(user_id=user_id,
                                            money=money,
                                            req_id=req_id)
            if body['data'][0]['status'] != "0":
                retry = True

        # retry
        if retry:
            try:
                __, body = self.external_client.put('/pay', body=_body)
                if body['code'] != "0":
                    raise Exception
            except Exception:
                msg = "Deduct external account(%s) failed, deduct money(%s), req_id(%s)" % \
                        (user_id, money, req_id)
                LOG.exception(msg)
                raise exception.DeductError(user_id=user_id,
                                            money=money,
                                            req_id=req_id)

    def get_external_balance(self, ctxt, user_id):
        if not self.external_client:
            return

        params = dict(accountNum=user_id)
        try:
            __, body = self.external_client.get('/getBalance',
                                                params=params)
            if body['code'] != "0":
                raise Exception
        except Exception:
            LOG.exception("Fail to get external balance of account: %s" % user_id)
            raise exception.GetBalanceFailed(user_id=user_id)
        return body
