from oslo_config import cfg

from gringotts.client import client
from gringotts.services import keystone


def get_gringclient(region_name=None):
    ks_cfg = cfg.CONF.keystone_authtoken
    auth_url = keystone.get_auth_url()
    c = client.Client(username=ks_cfg.admin_user,
                      password=ks_cfg.admin_password,
                      project_name=ks_cfg.admin_tenant_name,
                      auth_url=auth_url)
    return c


def check_avaliable(region_name=None):
    client = get_gringclient(region_name)
    client.get('/')


def get_accounts(region_name=None):
    client = get_gringclient(region_name)
    __, accounts = client.get('/accounts')

    # for compatibility
    try:
        return accounts['accounts']
    except Exception:
        return accounts
