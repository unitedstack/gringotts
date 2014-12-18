# -*- coding: utf-8 -*-
import json
import requests
import datetime

from keystoneclient.v3 import client


CLOUDS = {"mm": {"os_auth_url": "http://l7.0.mm.ustack.in:35357/v3",
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


def get_ks_client(cloud):
    ks_client = client.Client(user_domain_name="Default",
                              username=cloud['admin_user'],
                              password=cloud['admin_password'],
                              project_domain_name="Default",
                              project_name=cloud['admin_tenant_name'],
                              auth_url=cloud['os_auth_url'])
    ks_client.management_url = force_v3_api(ks_client.management_url)
    return ks_client


def get_gring_client(cloud):
    client = client.Client(username=cloud['admin_user'],
                           password=cloud['admin_password'],
                           project_name=cloud['admin_tenant_name'],
                           auth_url=cloud['os_auth_url'])
    return client


def get_project_id_list(ks_client):
    projects = ks_client.projects.list()
    project_ids = []
    for project in projects:
        project_ids.append(project['id'])

    return set(project_ids)


def get_account_id_list(gring_client):
    accounts = gring_client.get('/accounts/')[1]['accounts']
    account_ids = []

    for account in accounts:
        account_ids.append(account['project_id'])

    return set(account_ids)


for cloud_name, cloud in CLOUDS.items():
    ks_client = get_ks_client(cloud)
    gring_client = get_gring_client(cloud)
    diff = get_account_id_list(gring_client) - get_project_id_list(gring_client)
    print diff
