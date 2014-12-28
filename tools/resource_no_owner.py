# -*- coding: utf-8 -*-
import json
import requests
import datetime
import pprint

from gringotts.client import client as g_client
from keystoneclient.v3 import client as k_client

import  glanceclient
from cinderclient.v1 import client as cinder_client
from neutronclient.v2_0 import client as neutron_client
from novaclient.v1_1 import client as nova_client
from ceilometerclient import client as cmclient


CLOUDS = {"mm": {"os_auth_url": "http://l7.0.mm.ustack.in:35357/v3",
                 "regions": ["RegionOne"],
                 "admin_user": "admin",
                 "admin_password": "password",
                 "admin_tenant_name": "admin"},
          "zhj": {"os_auth_url": "http://l7.0.zhj.ustack.in:35357/v3",
                 "regions": ["RegionOne"],
                 "admin_user": "admin",
                 "admin_password": "password",
                 "admin_tenant_name": "admin"},
          "qn": {"os_auth_url": "http://l7.0.qn.ustack.in:35357/v3",
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


def force_v3_api(url):
    if url is None:
        return url
    if url.endswith('/v2.0'):
        return url.replace('/v2.0', '/v3')
    return url


def force_v1_api(url):
    if url is None:
        return url
    if url.endswith('/v2'):
        return url.replace('/v2', '/v1')
    return url


def get_ks_client(cloud):
    client = k_client.Client(user_domain_name="Default",
                             username=cloud['admin_user'],
                             password=cloud['admin_password'],
                             project_domain_name="Default",
                             project_name=cloud['admin_tenant_name'],
                             auth_url=cloud['os_auth_url'])
    client.management_url = force_v3_api(client.management_url)
    return client


def get_gring_client(cloud):
    client = g_client.Client(username=cloud['admin_user'],
                             password=cloud['admin_password'],
                             project_name=cloud['admin_tenant_name'],
                             auth_url=cloud['os_auth_url'])
    client.management_url = force_v1_api(client.management_url)
    return client


def get_admin_tenant_id(ks_client):
    return ks_client.project_id


def get_token(ks_client):
    return ks_client.auth_token


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


def server_list(ks_client, cloud, project_id=None, region_name=None):
    search_opts = {'all_tenants': 1}

    if project_id:
        search_opts.update(project_id=project_id)

    return get_novaclient(ks_client, cloud, region_name).servers.list(detailed=False,
                                                                      search_opts=search_opts)


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


def snapshot_list(ks_client, cloud, project_id, region_name=None):
    """To see all snapshots in the cloud as admin
    """
    c_client = get_cinderclient(ks_client, cloud, region_name)
    search_opts = {'all_tenants': 1,
                   'project_id': project_id}
    if c_client is None:
        return []
    snapshots = c_client.volume_snapshots.list(False, search_opts=search_opts)
    return snapshots


def get_neutronclient(ks_client, region_name=None):
    endpoint = get_endpoint(ks_client, region_name, 'network')
    auth_token = get_token(ks_client)
    c = neutron_client.Client(token=auth_token,
                              endpoint_url=endpoint)
    return c


def floatingip_list(ks_client, project_id=None, region_name=None):
    client = get_neutronclient(ks_client, region_name)
    if project_id:
        fips = client.list_floatingips(tenant_id=project_id).get('floatingips')
    else:
        fips = client.list_floatingips().get('floatingips')

    return fips


def subnet_list(ks_client, project_id=None, region_name=None):
    client = get_neutronclient(ks_client, region_name)
    if project_id:
        subnets = client.list_subnets(tenant_id=project_id).get('subnets')
    else:
        subnets = client.list_subnets().get('subnets')
    return subnets


def port_list(ks_client, project_id=None, region_name=None):
    client = get_neutronclient(ks_client, region_name)
    if project_id:
        ports = client.list_ports(tenant_id=project_id).get('ports')
    else:
        ports = client.list_ports().get('ports')

    return ports


def network_list(ks_client, project_id=None, region_name=None):
    client = get_neutronclient(ks_client, region_name)
    networks = client.list_networks(tenant_id=project_id).get('networks')
    return networks


def router_list(ks_client, project_id, region_name=None):
    client = get_neutronclient(ks_client, region_name)
    if project_id:
        routers = client.list_routers(tenant_id=project_id).get('routers')
    else:
        routers = client.list_routers().get('routers')
    return routers


def sg_list(ks_client, project_id, region_name=None):
    client = get_neutronclient(ks_client, region_name)
    if project_id:
        sgs = client.list_security_groups(tenant_id=project_id).get('security_groups')
    else:
        sgs = client.list_security_groups().get('security_groups')
    return sgs


def get_cmclient(ks_client, region_name=None):
    endpoint = get_endpoint(ks_client, region_name, 'metering')
    auth_token = get_token(ks_client)
    return cmclient.get_client(2,
                               os_auth_token=(lambda: auth_token),
                               ceilometer_url=endpoint)


def alarm_list(ks_client, project_id, region_name=None):
    alarms = get_cmclient(ks_client, region_name).alarms.list(q=[{'field': 'project_id',
                                                                  'value': project_id}])
    return alarms


def get_glanceclient(ks_client, region_name=None):
    endpoint = get_endpoint(ks_client, region_name, 'image')
    if endpoint[-1] != '/':
        endpoint += '/'
    auth_token = get_token(ks_client)
    return glanceclient.Client('2', endpoint, token=auth_token)


def image_list(ks_client, project_id, region_name=None):
    filters = {'owner': project_id}
    images = get_glanceclient(ks_client, region_name).images.list(filters=filters)
    return images


def get_project_id_list(ks_client):
    projects = ks_client.projects.list()
    project_ids = []
    for project in projects:
        project_ids.append(project.id)

    return set(project_ids)


def get_account_id_list(gring_client):
    accounts = gring_client.get('/accounts/')[1]
    account_ids = []

    for account in accounts:
        account_ids.append(account['project_id'])

    return set(account_ids)


for cloud_name, cloud in CLOUDS.items():
    print "Cloud: %s" % cloud_name
    ks_client = get_ks_client(cloud)
    gring_client = get_gring_client(cloud)
    diff = get_account_id_list(gring_client) - get_project_id_list(ks_client)

    for project_id in diff:
        print "Project: %s" % project_id
        for region_name in cloud['regions']:
            servers = server_list(ks_client, cloud, project_id=project_id, region_name=region_name)
            volumes = volume_list(ks_client, cloud, project_id=project_id, region_name=region_name)
            snapshots = snapshot_list(ks_client, cloud, project_id, region_name=region_name)
            fips = floatingip_list(ks_client, project_id=project_id, region_name=region_name)
            subnets = subnet_list(ks_client, project_id=project_id, region_name=region_name)
            networks = network_list(ks_client, project_id=project_id, region_name=region_name)
            ports = port_list(ks_client, project_id=project_id, region_name=region_name)
            routers = router_list(ks_client, project_id=project_id, region_name=region_name)
            sgs = sg_list(ks_client, project_id=project_id, region_name=region_name)
            alarms = alarm_list(ks_client, project_id, region_name=region_name)
            images = image_list(ks_client, project_id, region_name=region_name)

            for server in servers:
                print "Instance", server.id, server.name
            for volume in volumes:
                print "Volume", volume.id, volume.display_name
            for snapshot in snapshots:
                print "Snapshot", snapshot.id, snapshot.display_name
            for fip in fips:
                print "Fip", fip['id'], fip['uos:name']
            for subnet in subnets:
                print "Subnet", subnet['id'], subnet['name']
            for network in networks:
                print "Network", network['id'], network['name']
            for port in ports:
                print "Port", port['id'], port['name']
            for router in routers:
                print "Router", router['id'], router["name"]
            for sg in sgs:
                print "SecurityGroup", sg['id'], sg['name']
            for alarm in alarms:
                 print "Alarm", alarm.alarm_id, alarm.name
            for image in images:
                 print "Image", image.id, image.name
