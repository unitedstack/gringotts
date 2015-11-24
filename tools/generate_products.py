import argparse
import json
import os
import sys
import requests

from gringotts.client import client as gring_client
from novaclient.v1_1 import client as nova_client


parser = argparse.ArgumentParser(description='Generate products')
parser.add_argument('--username',
                    metavar='OS_USERNAME',
                    default=os.environ.get('OS_USERNAME', 'admin'),
                    help='User name to use for OpenStack service access.')
parser.add_argument('--password',
                    metavar='OS_PASSWORD',
                    default=os.environ.get('OS_PASSWORD', 'admin'),
                    help='Password to use for OpenStack service access.')
parser.add_argument('--tenant_name',
                    metavar='OS_TENANT_NAME',
                    default=os.environ.get('OS_TENANT_NAME', 'admin'),
                    help='Tenant name to use for OpenStack service access.')
parser.add_argument('--auth_url',
                    metavar='OS_AUTH_URL',
                    default=os.environ.get('OS_AUTH_URL', 'http://localhost:35357/v3'),
                    help='Auth URL to use for OpenStack service access.')
parser.add_argument('--recreate_flavor',
                    metavar='BOOL', type=bool, default=False,
                    help='Recreate flavor or not')
args = parser.parse_args()


def force_v3_api(url):
    if url is None:
        return url
    return url.replace('/v2.0', '/v3')


gc = gring_client.Client(username=args.username,
                         password=args.password,
                         project_name=args.tenant_name,
                         auth_url=force_v3_api(args.auth_url))


nc = nova_client.Client(username=args.username,
                        api_key=args.password,
                        project_id=args.tenant_name,
                        auth_url=args.auth_url)


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


def make_seg_price(hourly_price=None, monthly_price=None,
                   yearly_price=None):
    seg = {}
    if hourly_price:
        seg.update({"price": {
            "base_price": hourly_price[0],
            "type": "segmented",
            "segmented": hourly_price[1]
        }})
    if monthly_price:
        seg.update({"monthly_price": {
            "base_price": monthly_price[0],
            "type": "segmented",
            "segmented": monthly_price[1]
        }})
    if yearly_price:
        seg.update({"yearly_price": {
            "base_price": yearly_price[0],
            "type": "segmented",
            "segmented": yearly_price[1]
        }})
    return json.dumps(seg) if seg else None



if __name__ == '__main__':
    if args.recreate_flavor:
        clear_flavors()
        flavors = [
            ('micro-1', 512, 1, 20),
            ('micro-2', 1024, 1, 20),
            ('standard-1', 2048, 1, 20),
            ('standard-2', 4096, 2, 20),
            ('standard-4', 8192, 4, 20),
            ('standard-8', 16384, 8, 20),
            ('standard-12', 24576, 12, 20),
            ('standard-16', 32768, 16, 20),
            ('memory-1', 4096, 1, 20),
            ('memory-2', 8192, 2, 20),
            ('memory-4', 16384, 4, 20),
            ('memory-8', 32768, 8, 20),
            ('memory-12', 49152, 12, 20),
            ('compute-2', 2048, 2, 20),
            ('compute-4', 4096, 4, 20),
            ('compute-8', 8192, 8, 20),
            ('compute-12', 12288, 12, 20),
        ]
        for name, ram, vcpus, disk in flavors:
            create_flavor(name, ram, vcpus, disk)

    # ip
    seg_ip_bgp = make_seg_price(
        ("0", [[100, "0.3611"], [50, "0.2778"], [30, "0.2222"], [0, "0.0300"]]),
        ("0", [[100, "200"], [50, "150"], [30, "140"], [0, "20"]]),
        ("0", [[100, "2000"], [50, "1500"], [30, "1400"], [0, "200"]]))
    seg_ip_tel = make_seg_price(
        ("0", [[100, "0.3611"], [50, "0.2778"], [30, "0.2222"], [0, "0.0300"]]),
        ("0", [[100, "200"], [50, "150"], [30, "140"], [0, "20"]]),
        ("0", [[100, "2000"], [50, "1500"], [30, "1400"], [0, "200"]]))

    # instance
    instance_micro_1 = make_seg_price(
        ("0", [[0, "0.0560"]]),
        ("0", [[0, "40"]]),
        ("0", [[0, "400"]]))
    instance_micro_2 = make_seg_price(
        ("0", [[0, "0.1110"]]),
        ("0", [[0, "70"]]),
        ("0", [[0, "700"]]))
    instance_standard_1 = make_seg_price(
        ("0", [[0, "0.2220"]]),
        ("0", [[0, "150"]]),
        ("0", [[0, "1500"]]))
    instance_standard_2 = make_seg_price(
        ("0", [[0, "0.4440"]]),
        ("0", [[0, "300"]]),
        ("0", [[0, "3000"]]))
    instance_standard_4 = make_seg_price(
        ("0", [[0, "0.8890"]]),
        ("0", [[0, "600"]]),
        ("0", [[0, "6000"]]))
    instance_standard_8 = make_seg_price(
        ("0", [[0, "1.7780"]]),
        ("0", [[0, "1200"]]),
        ("0", [[0, "12000"]]))
    instance_standard_12 = make_seg_price(
        ("0", [[0, "2.6670"]]),
        ("0", [[0, "1900"]]),
        ("0", [[0, "19000"]]))
    instance_standard_16 = make_seg_price(
        ("0", [[0, "3.5560"]]),
        ("0", [[0, "2500"]]),
        ("0", [[0, "25000"]]))
    instance_memory_1 = make_seg_price(
        ("0", [[0, "0.3610"]]),
        ("0", [[0, "250"]]),
        ("0", [[0, "2500"]]))
    instance_memory_2 = make_seg_price(
        ("0", [[0, "0.7220"]]),
        ("0", [[0, "500"]]),
        ("0", [[0, "5000"]]))
    instance_memory_4 = make_seg_price(
        ("0", [[0, "1.4440"]]),
        ("0", [[0, "1000"]]),
        ("0", [[0, "10000"]]))
    instance_memory_8 = make_seg_price(
        ("0", [[0, "2.8890"]]),
        ("0", [[0, "2000"]]),
        ("0", [[0, "20000"]]))
    instance_memory_12 = make_seg_price(
        ("0", [[0, "4.3330"]]),
        ("0", [[0, "3000"]]),
        ("0", [[0, "30000"]]))
    instance_compute_2 = make_seg_price(
        ("0", [[0, "0.3330"]]),
        ("0", [[0, "200"]]),
        ("0", [[0, "20000"]]))
    instance_compute_4 = make_seg_price(
        ("0", [[0, "0.6670"]]),
        ("0", [[0, "450"]]),
        ("0", [[0, "4500"]]))
    instance_compute_8 = make_seg_price(
        ("0", [[0, "2.8890"]]),
        ("0", [[0, "2000"]]),
        ("0", [[0, "20000"]]))
    instance_compute_12 = make_seg_price(
        ("0", [[0, "2.0000"]]),
        ("0", [[0, "1400"]]),
        ("0", [[0, "14000"]]))

    # volume
    volume_size = make_seg_price(
        ("0", [[0, "0.0020"]]),
        ("0", [[0, "1.4"]]),
        ("0", [[0, "14"]]))
    sata_volume_size = make_seg_price(
        ("0", [[0, "0.0006"]]),
        ("0", [[0, "0.4"]]),
        ("0", [[0, "4"]]))

    products = [
        ('instance:micro-1', 'compute', 'test1', '0.0560', instance_micro_1),
        ('instance:micro-2', 'compute', 'test1', '0.1110', instance_micro_2),
        ('instance:standard-1', 'compute', 'test1', '0.222', instance_standard_1),
        ('instance:standard-2', 'compute', 'test1', '0.444', instance_standard_2),
        ('instance:standard-4', 'compute', 'test1', '0.889', instance_standard_4),
        ('instance:standard-8', 'compute', 'test1', '1.778', instance_standard_8),
        ('instance:standard-12', 'compute', 'test1', '2.667', instance_standard_12),
        ('instance:standard-16', 'compute', 'test1', '3.556', instance_standard_16),
        ('instance:memory-1', 'compute', 'test1', '0.3610', instance_memory_1),
        ('instance:memory-2', 'compute', 'test1', '0.7220', instance_memory_2),
        ('instance:memory-4', 'compute', 'test1', '1.4440', instance_memory_4),
        ('instance:memory-8', 'compute', 'test1', '2.8890', instance_memory_8),
        ('instance:memory-12', 'compute', 'test1', '4.3330', instance_memory_12),
        ('instance:compute-2', 'compute', 'test1', '0.3330', instance_compute_2),
        ('instance:compute-4', 'compute', 'test1', '0.6670', instance_compute_4),
        ('instance:compute-8', 'compute', 'test1', '2.8890', instance_compute_8),
        ('instance:compute-12', 'compute', 'test1', '2.000', instance_compute_12),
        ('ip.floating.CHINATELECOM', 'network', 'test1', '0.0347', seg_ip_tel),
        ('ip.floating.BGP', 'network', 'test1', '0.0347', seg_ip_bgp),
        ('volume.size', 'block_storage', 'test1', '0.0020', volume_size),
        ('sata.volume.size', 'block_storage', 'test1', '0.0006', sata_volume_size),
        ('snapshot.size', 'block_storage', 'test1', '0.0002', None),
        ('listener', 'network', 'test1', '0.03', None),
        ('alarm', 'monitor', 'test1', '0.03', None),
    ]
    for name, service, region_id, unit_price, extra in products:
        try:
            create_or_update_product(name, service, region_id, unit_price, extra)
        except Exception:
            raise
