# -*- coding: utf-8 -*-
import json
import requests
import datetime

from keystoneclient.v3 import client
from cinderclient.v1 import client as cinder_client
from neutronclient.v2_0 import client as neutron_client
from novaclient.v1_1 import client as nova_client


CLOUDS = {"uos": {"os_auth_url": "http://i.l7.0.uc.ustack.in:35357/v3",
                  "regions": ["RegionOne", "zhsh"],
                  "admin_user": "admin",
                  "admin_password": "password",
                  "admin_tenant_name": "admin"},
          "mm": {"os_auth_url": "http://l7.0.mm.ustack.in:35357/v3",
                 "regions": ["RegionOne"],
                 "admin_user": "admin",
                 "admin_password": "password",
                 "admin_tenant_name": "admin"},
          "zhj": {"os_auth_url": "http://l7.0.zhj.ustack.in:35357/v3",
                 "regions": ["RegionOne"],
                 "admin_user": "admin",
                 "admin_password": "password",
                 "admin_tenant_name": "admin"},
          "sh": {"os_auth_url": "http://l7.0.sh.ustack.in:35357/v3",
                 "regions": ["RegionOne"],
                 "admin_user": "admin",
                 "admin_password": "password",
                 "admin_tenant_name": "admin"},
}


def wrap_exception(default_return_value=[]):
    def wrapper(f):
        def inner(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception:
                return default_return_value
        return inner
    return wrapper


def force_v3_api(url):
    if url is None:
        return url
    if url.endswith('/v2.0'):
        return url.replace('/v2.0', '/v3')
    return url


def get_ks_client(cloud):
    ks_client = client.Client(user_domain_name="Default",
                              username=cloud['admin_user'],
                              password=cloud['admin_password'],
                              project_domain_name="Default",
                              project_name=cloud['admin_tenant_name'],
                              auth_url=cloud['os_auth_url'])
    ks_client.management_url = force_v3_api(ks_client.management_url)
    return ks_client


def get_token(ks_client):
    return ks_client.auth_token


def get_admin_tenant_id(ks_client):
    return ks_client.project_id


@wrap_exception()
def get_user_list(ks_client):
    return ks_client.users.list()


@wrap_exception()
def get_project_list(ks_client):
    return ks_client.projects.list()


def _get_catalog(ks_client):
    try:
        endpoints = ks_client.endpoints.list()
        services = ks_client.services.list()
    except Exception as e:
        LOG.exception('failed to load endpoints from kesytone:%s' % e)
        return []

    catalog = []

    for service in services:
        _endpoints = []
        for endpoint in endpoints:
            if endpoint.service_id == service.id:
                url=force_v3_api(endpoint.url) if service.type=='identity' else endpoint.url
                _endpoints.append(dict(id=endpoint.id,
                                       interface=endpoint.interface,
                                       url=url,
                                       region=endpoint.region))
        _service = dict(id=service.id,
                        type=service.type,
                        endpoints=_endpoints)

        catalog.append(_service)

    return catalog


def get_endpoint(ks_client, region_name, service_type):
    catalog = _get_catalog(ks_client)

    endpoint_type = 'admin'
    project_id = get_admin_tenant_id(ks_client)

    for service in catalog:
        if service['type'] != service_type:
            continue

        endpoints = service['endpoints']
        for endpoint in endpoints:
            if endpoint.get('interface') != endpoint_type:
                continue
            if region_name and endpoint.get('region') != region_name:
                continue
            return (endpoint['url'].replace('$', '%') %
                    {'tenant_id': project_id, 'project_id': project_id})


def get_novaclient(ks_client, cloud, region_name=None):
    endpoint = get_endpoint(ks_client, region_name, 'compute')
    auth_token = get_token(ks_client)

    c = nova_client.Client(cloud['admin_user'],
                           cloud['admin_password'],
                           None, # project_id is not required
                           auth_url=cloud['os_auth_url'])

    # Give auth_token and management_url directly to avoid authenticate again.
    c.client.auth_token = auth_token
    c.client.management_url = endpoint
    return c


@wrap_exception()
def server_list(ks_client, cloud, project_id=None, region_name=None):
    search_opts = {'all_tenants': 1}

    if project_id:
        search_opts.update(project_id=project_id)

    return get_novaclient(ks_client, cloud, region_name).servers.list(detailed=False,
                                                                      search_opts=search_opts)


@wrap_exception(0)
def server_number(ks_client, cloud, region_name=None):
    return get_novaclient(ks_client, cloud, region_name).hypervisors.statistics().running_vms


def get_cinderclient(ks_client, cloud, region_name=None):
    endpoint = get_endpoint(ks_client, region_name, 'volume')
    auth_token = get_token(ks_client)
    c = cinder_client.Client(cloud['admin_user'],
                             cloud['admin_password'],
                             None,
                             auth_url=cloud['os_auth_url'])
    c.client.auth_token = auth_token
    c.client.management_url = endpoint
    return c


@wrap_exception()
def volume_list(ks_client, cloud, project_id=None, region_name=None):
    """To see all volumes in the cloud as admin.
    """
    c_client = get_cinderclient(ks_client, cloud, region_name)
    search_opts = {'all_tenants': 1}
    if project_id:
       search_opts.update(project_id=project_id)
    if c_client is None:
        return []
    return c_client.volumes.list(detailed=False, search_opts=search_opts)


def get_neutronclient(ks_client, region_name=None):
    endpoint = get_endpoint(ks_client, region_name, 'network')
    auth_token = get_token(ks_client)
    c = neutron_client.Client(token=auth_token,
                              endpoint_url=endpoint)
    return c


@wrap_exception()
def floatingip_list(ks_client, project_id=None, region_name=None):
    client = get_neutronclient(ks_client, region_name)
    if project_id:
        fips = client.list_floatingips(tenant_id=project_id).get('floatingips')
    else:
        fips = client.list_floatingips().get('floatingips')

    return fips


today = datetime.date.today()

# send email
content = u""
for cloud_name, cloud in CLOUDS.items():
    ks_client = get_ks_client(cloud)

    users = get_user_list(ks_client)
    projects = get_project_list(ks_client)
    content += u"<p>%s云, 用户数: %s, 项目数：%s</p>" % (cloud_name, len(users), len(projects))

    content += u"<table border=\"1\" style=\"border-collapse:collapse;\"><thead><tr><th>区域</th><th>主机</th><th>云硬盘</th><th>公网IP</th></tr></thead>"
    for region_name in cloud['regions']:
        server_num = server_number(ks_client, cloud, region_name=region_name)
        volumes = volume_list(ks_client, cloud, region_name=region_name)
        fips = floatingip_list(ks_client, region_name=region_name)

        content += u"<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % \
                    (region_name, server_num, len(volumes), len(fips))
    content += u"</table><br/>"

url="https://sendcloud.sohu.com/webapi/mail.send.xml"

params = {"api_user": "postmaster@unitedstack-trigger.sendcloud.org",
          "api_key": "7CVvlTcXvVDgMo8U",
          "from": "notice@mail.unitedstack.com",
          "fromname": "UnitedStack",
          #"to": "support@unitedstack.com",
          "to": ["guangyu@unitedstack.com", "578579544@qq.com"],
          "subject": '[UnitedStack][%s]资源报表' % today,
          "template_invoke_name": "register",
          "html": content.encode('utf-8')}

r = requests.post(url, data=params)
