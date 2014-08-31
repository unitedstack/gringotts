from oslo.config import cfg

from gringotts.client import client
from gringotts.services import keystone as ks_client
from gringotts.openstack.common import log


LOG = log.getLogger(__name__)


def get_gringclient(region_name=None):
    os_cfg = cfg.CONF.service_credentials
    endpoint = ks_client.get_endpoint(region_name, 'billing')
    c = client.Client(username=os_cfg.os_username,
                      password=os_cfg.os_password,
                      project_name=os_cfg.os_tenant_name,
                      auth_url=os_cfg.os_auth_url)
    c.management_url = endpoint
    return c


def check_avaliable(region_name=None):
    client = get_gringclient(region_name)
    result = client.get('/')


def get_accounts(region_name=None):
    client = get_gringclient(region_name)
    __, accounts = client.get('/accounts')

    # for compatibility
    try:
        return accounts['accounts']
    except Exception:
        return accounts
