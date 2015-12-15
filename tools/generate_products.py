import argparse
import json
import os
import sys
import requests

from decimal import Decimal, ROUND_HALF_UP
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


def quantize(value):
    if isinstance(value, Decimal):
        return value.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)


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


def _generate_seg_price(base_seg_price, times):
    result = []
    for price in base_seg_price:
        result.append([price[0], str(times * quantize(price[1]))])
    return result


def make_seg_price(hourly_price=None, monthly_price=None,
                   yearly_price=None, auto_generated=True):
    seg = {}
    if hourly_price:
        seg.update({"price": {
            "base_price": hourly_price[0],
            "type": "segmented",
            "segmented": hourly_price[1]
        }})
    if hourly_price and (monthly_price or auto_generated):
        if not monthly_price:
            monthly_price = (hourly_price[0],
                             _generate_seg_price(hourly_price[1], 720))
        seg.update({"monthly_price": {
            "base_price": monthly_price[0],
            "type": "segmented",
            "segmented": monthly_price[1]
        }})
    if monthly_price and (yearly_price or auto_generated):
        if not yearly_price:
            yearly_price = (monthly_price[0],
                            _generate_seg_price(monthly_price[1], 12))
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

    seg_ip_bgp = {"hourly_price": ("0", [[100, "0.3611"], [50, "0.2778"], [30, "0.2222"], [0, "0.0300"]])}
    products = [
        ('instance:micro-1', 'compute', 'test1', '0.0560', None),
        ('instance:micro-2', 'compute', 'test1', '0.1110', None),
        ('instance:standard-1', 'compute', 'test1', '0.222', None),
        ('instance:standard-2', 'compute', 'test1', '0.444', None),
        ('instance:standard-4', 'compute', 'test1', '0.889', None),
        ('instance:standard-8', 'compute', 'test1', '1.778', None),
        ('instance:standard-12', 'compute', 'test1', '2.667', None),
        ('instance:standard-16', 'compute', 'test1', '3.556', None),
        ('instance:memory-1', 'compute', 'test1', '0.3610', None),
        ('instance:memory-2', 'compute', 'test1', '0.7220', None),
        ('instance:memory-4', 'compute', 'test1', '1.4440', None),
        ('instance:memory-8', 'compute', 'test1', '2.8890', None),
        ('instance:memory-12', 'compute', 'test1', '4.3330', None),
        ('instance:compute-2', 'compute', 'test1', '0.3330', None),
        ('instance:compute-4', 'compute', 'test1', '0.6670', None),
        ('instance:compute-8', 'compute', 'test1', '2.8890', None),
        ('instance:compute-12', 'compute', 'test1', '2.000', None),
        ('ip.floating.BGP', 'network', 'test1', '0.0347', seg_ip_bgp),
        ('volume.size', 'block_storage', 'test1', '0.0020', None),
        ('sata.volume.size', 'block_storage', 'test1', '0.0006', None),
        ('snapshot.size', 'block_storage', 'test1', '0.0002', None),
        ('listener', 'network', 'test1', '0.03', None),
        ('alarm', 'monitor', 'test1', '0.03', None),
    ]
    for name, service, region_id, unit_price, extra in products:
        try:
            if not extra:
                extra = {"hourly_price": ("0", [[0, unit_price]])}
            extra = make_seg_price(**extra)
            create_or_update_product(name, service, region_id, unit_price, extra)
        except Exception:
            raise
