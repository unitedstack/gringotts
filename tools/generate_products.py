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


def create_or_update_product(name, service, region_id, unit_price, extra=None):
    params = dict(name=name,
                  service=service,
                  region_id=region_id)
    resp, product = gc.get('/products/detail', params=params)

    body = dict(name=name,
                service=service,
                region_id=region_id,
                unit_price=unit_price,
                type="regular",
                unit="hour",
                description="some desc",
                extra=extra)

    if product['products']:
        gc.put('/products/%s' % product['products'][0]['product_id'],
               body=body)
    else:
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


def clear_flavors():
    flavors = nc.flavors.list()
    for flavor in flavors:
        nc.flavors.delete(flavor.id)


if __name__ == '__main__':
    clear_flavors()
    flavors = [
        ('micro-2', 1024, 1, 20),
        ('standard-1', 2048, 1, 20),
        ('memory-1', 4096, 1, 20),
        ('memory-2', 8192, 1, 20),
        ('compute-2', 2048, 2, 20),
        ('standard-2', 4096, 2, 20),
        ('memory-3', 8192, 2, 20),
        ('memory-4', 16384, 2, 20),
        ('compute-4', 4096, 4, 20),
        ('standard-4', 8192, 4, 20),
        ('memory-5', 16384, 4, 20),
        ('memory-6', 32768, 4, 20),
        ('compute-8', 8192, 8, 20),
        ('standard-8', 16384, 8, 20),
        ('memory-7', 32768, 8, 20),
        ('standard-12', 65536, 8, 20),
        ('compute-12', 16384, 16, 20),
        ('standard-16', 32768, 16, 20),
        ('standard-32', 65536, 16, 20),
    ]
    for name, ram, vcpus, disk in flavors:
        create_flavor(name, ram, vcpus, disk)

    seg_ip_xm1 = {
        "price": {
            "base_price": "0",
            "type": "segmented",
            "segmented": [[6, "0.0556"], [0, "0.0347"]]
        }
    }
    seg_ip_tw1 = {
        "price": {
            "base_price": "0",
            "type": "segmented",
            "segmented": [[6, "0.25"], [0, "0.0833"]]
        }
    }
    products = [
        ('instance:micro-2', 'compute', 'xm1', '0.111', None), # 4c 2g
        ('instance:standard-1', 'compute', 'xm1', '0.222', None), # 4c 12g
        ('instance:memory-1', 'compute', 'xm1', '0.333', None), # 8c 6g
        ('instance:memory-2', 'compute', 'xm1', '0.555', None), # 8c 12g
        ('instance:compute-2', 'compute', 'xm1', '0.333', None), # 8c 24g
        ('instance:standard-2', 'compute', 'xm1', '0.444', None), # 8c 32g
        ('instance:memory-3', 'compute', 'xm1', '0.722', None), # 12c 8g
        ('instance:memory-4', 'compute', 'xm1', '1.278', None), # 12c 16g
        ('instance:compute-4', 'compute', 'xm1', '0.667', None), # 12c 32g
        ('instance:standard-4', 'compute', 'xm1', '0.889', None), # 16c 16g
        ('instance:memory-5', 'compute', 'xm1', '1.444', None), # 16c 24g
        ('instance:memory-6', 'compute', 'xm1', '2.554', None), # 16c 48g
        ('instance:compute-8', 'compute', 'xm1', '1.333', None), # 16c 48g
        ('instance:standard-8', 'compute', 'xm1', '1.778', None), # 16c 48g
        ('instance:memory-7', 'compute', 'xm1', '2.889', None), # 16c 48g
        ('instance:standard-12', 'compute', 'xm1', '5.111', None), # 16c 48g
        ('instance:compute-12', 'compute', 'xm1', '2.445', None), # 16c 48g
        ('instance:standard-16', 'compute', 'xm1', '3.556', None), # 16c 48g
        ('instance:tandard-32', 'compute', 'xm1', '5.778', None), # 16c 48g
        ('ip.floatingip.TELECOM', 'network', 'xm1', '0.0347', json.dumps(seg_ip_xm1)),
        ('volume.size', 'block_storage', 'xm1', '0.0020', None),
        ('sata.volume.size', 'block_storage', 'xm1', '0.0006', None),
        ('snapshot.size', 'block_storage', 'xm1', '0.0002', None),
        ('listener', 'network', 'xm1', '0.03', None),
        ('alarm', 'monitor', 'xm1', '0.03', None),

        ('instance:micro-2', 'compute', 'tw1', '0.133', None), # 4c 2g
        ('instance:standard-1', 'compute', 'tw1', '0.266', None), # 4c 12g
        ('instance:memory-1', 'compute', 'tw1', '0.400', None), # 8c 6g
        ('instance:memory-2', 'compute', 'tw1', '0.667', None), # 8c 12g
        ('instance:compute-2', 'compute', 'tw1', '0.400', None), # 8c 24g
        ('instance:standard-2', 'compute', 'tw1', '0.533', None), # 8c 32g
        ('instance:memory-3', 'compute', 'tw1', '0.866', None), # 12c 8g
        ('instance:memory-4', 'compute', 'tw1', '1.534', None), # 12c 16g
        ('instance:compute-4', 'compute', 'tw1', '0.800', None), # 12c 32g
        ('instance:standard-4', 'compute', 'tw1', '1.067', None), # 16c 16g
        ('instance:memory-5', 'compute', 'tw1', '1.733', None), # 16c 24g
        ('instance:memory-6', 'compute', 'tw1', '3.065', None), # 16c 48g
        ('instance:compute-8', 'compute', 'tw1', '1.600', None), # 16c 48g
        ('instance:standard-8', 'compute', 'tw1', '2.134', None), # 16c 48g
        ('instance:memory-7', 'compute', 'tw1', '3.467', None), # 16c 48g
        ('instance:standard-12', 'compute', 'tw1', '6.133', None), # 16c 48g
        ('instance:compute-12', 'compute', 'tw1', '2.934', None), # 16c 48g
        ('instance:standard-16', 'compute', 'tw1', '4.267', None), # 16c 48g
        ('instance:tandard-32', 'compute', 'tw1', '6.934', None), # 16c 48g
        ('ip.floatingip.TELECOM', 'network', 'tw1', '0.0833', json.dumps(seg_ip_tw1)),
        ('volume.size', 'block_storage', 'tw1', '0.0025', None),
        ('sata.volume.size', 'block_storage', 'tw1', '0.0007', None),
        ('snapshot.size', 'block_storage', 'tw1', '0.0003', None),
        ('listener', 'network', 'tw1', '0.0361', None),
        ('alarm', 'monitor', 'tw1', '0.0361', None),
    ]
    for name, service, region_id, unit_price, extra in products:
        try:
            create_or_update_product(name, service, region_id, unit_price, extra)
        except Exception:
            raise
