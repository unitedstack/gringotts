import sys
import json
import requests
from gringotts.client import client as gring_client
from novaclient.v1_1 import client as nova_client


gc = gring_client.Client(username='admin',
                         password='rachel',
                         project_name='admin',
                         auth_url='http://localhost:35357/v3')


nc = nova_client.Client(username='admin',
                        api_key='rachel',
                        project_id='admin',
                        auth_url='http://localhost:35357/v2.0')


def create_product(name, service, region_id, unit_price):
    body = dict(name=name,
                service=service,
                region_id=region_id,
                unit_price=unit_price,
                type="regular",
                unit="hour",
                description="some desc")
    gc.post('/products', body=body)


def _set_flavor_key(flavor_id, **meta):
    if not nc.client.management_url:
        nc.authenticate()
    endpoint = nc.client.management_url
    url = "%s/flavors/%s/os-extra_specs" % (endpoint, flavor_id)
    headers = {
        "X-Auth-Token": nc.client.auth_token,
        "Content-Type": "application/json",
    }
    body = {
        "extra_specs": meta
    }
    requests.post(url, data=json.dumps(body), headers=headers)


def create_flavor(name, ram, vcpus, disk):
    flavor = nc.flavors.create(name, ram, vcpus, disk)
    meta = {'hw_video:ram_max_mb': 64}
    _set_flavor_key(flavor.id, **meta)


"""
>>> 1024 * 6
6144
>>> 1024 * 8
8192
>>> 1024 * 16
16384
>>> 1024 * 24
24576
>>> 1024 * 32
32768
>>> 1024 * 48
49152
"""

if __name__ == '__main__':
    products = [
        ('compute-1', 'compute', 'RegionOne', '0.1109', 1024, 2, 20), # 2c 1g
        ('compute-3', 'compute', 'RegionOne', '0.2218', 2048, 4, 20), # 4c 2g
        ('memory-3', 'compute', 'RegionOne', '1.0548', 12288, 4, 20), # 4c 12g
        ('compute-7', 'compute', 'RegionOne', '0.6102', 6144, 8, 20), # 8c 6g
        ('standard-7', 'compute', 'RegionOne', '1.1100', 12288, 8, 20), # 8c 12g
        ('memory-7', 'compute', 'RegionOne', '2.1096', 24576, 8, 20), # 8c 24g
        ('memory-8', 'compute', 'RegionOne', '2.7760', 32768, 8, 20), # 8c 32g
        ('compute-11', 'compute', 'RegionOne', '0.8320', 8192, 12, 20), # 12c 8g
        ('standard-11', 'compute', 'RegionOne', '1.4984', 16384, 12, 20), # 12c 16g
        ('memory-11', 'compute', 'RegionOne', '2.8312', 32768, 12, 20), # 12c 32g
        ('memory-13', 'compute', 'RegionOne', '1.5536', 16384, 16, 20), # 16c 16g
        ('standard-15', 'compute', 'RegionOne', '2.2200', 24576, 16, 20), # 16c 24g
        ('memory-15', 'compute', 'RegionOne', '4.2192', 49152, 16, 20), # 16c 48g
    ]
    for name, service, region_id, unit_price, ram, vcpus, disk in products:
        try:
            create_product(name, service, region_id, unit_price)
            #create_flavor(name, ram, vcpus, disk)
        except Exception:
            pass
