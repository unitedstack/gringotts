import argparse
import json
import os

from decimal import Decimal, ROUND_HALF_UP
from gringotts.client import client as gring_client
from keystoneclient.auth.identity import v3
from keystoneclient import session as ksc_session
from novaclient import client as nova_client


parser = argparse.ArgumentParser(description='Generate products')
parser.add_argument('--username',
                    metavar='OS_USERNAME',
                    default=os.environ.get('OS_USERNAME', 'admin'),
                    help='User name to use for OpenStack service access.')
parser.add_argument('--password',
                    metavar='OS_PASSWORD',
                    default=os.environ.get('OS_PASSWORD', 'admin'),
                    help='Password to use for OpenStack service access.')
parser.add_argument('--user_domain_id',
                    metavar='USER_DOMAIN_ID',
                    default=os.environ.get('OS_USER_DOMAIN_ID', 'default'),
                    help='User domain id to use for OpenStack service access.')
parser.add_argument('--project_domain_id',
                    metavar='PROJECT_DOMAIN_ID',
                    default=os.environ.get('OS_PROJECT_DOMAIN_ID', 'default'),
                    help='Project domain id to use for OpenStack service access.')
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
parser.add_argument('--region_name',
                    metavar='region_name',
                    default='RegionOne',
                    help='The region name of OpenStack service')
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


def get_session():
    keystone_host = args.auth_url
    auth = v3.Password(
        auth_url=keystone_host,
        username=args.username,
        password=args.password,
        project_name=args.tenant_name,
        user_domain_id=args.user_domain_id,
        project_domain_id=args.project_domain_id)
    session = ksc_session.Session(auth=auth)
    return session


def get_client():
    n_client = nova_client.Client(version=2,
    session=get_session(),
    region_name=args.region_name)
    return n_client

nc = get_client()

def create_or_update_product(name, service, region_id, unit_price):
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
                description="some desc")

    if product['products']:
        gc.put('/products/%s' % product['products'][0]['product_id'],
               body=body)
    else:
        gc.post('/products', body=body)


def create_flavor(name, ram, vcpus, disk):
    flavor = nc.flavors.create(name, ram, vcpus, disk)
    meta = {'hw_video:ram_max_mb':'64'}
    flavor.set_keys(meta)


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

    region = args.region_name
    def get_unit_price(data):
        segmented = []
        for s in data:
            segmented.append({'count': s[0], 'price': s[1]})
        unit_price = {"price":{"base_price": "0",
                               "type": "segmented",
                               "segmented": segmented}}
        return unit_price
    products = [
        ('instance:micro-1', 'compute', region, get_unit_price([[0, '0.0560']])),
        ('instance:micro-2', 'compute', region, get_unit_price([[0, '0.1110']])),
        ('instance:standard-1', 'compute', region, get_unit_price([[0, '0.2220']])),
        ('instance:standard-2', 'compute', region, get_unit_price([[0, '0.4440']])),
        ('instance:standard-4', 'compute', region, get_unit_price([[0, '0.8890']])),
        ('instance:standard-8', 'compute', region, get_unit_price([[0, '1.7780']])),
        ('instance:standard-12', 'compute', region, get_unit_price([[0, '2.6670']])),
        ('instance:standard-16', 'compute', region, get_unit_price([[0, '3.5560']])),
        ('instance:memory-1', 'compute', region, get_unit_price([[0, '0.3610']])),
        ('instance:memory-2', 'compute', region, get_unit_price([[0, '0.7220']])),
        ('instance:memory-4', 'compute', region, get_unit_price([[0, '1.4440']])),
        ('instance:memory-8', 'compute', region, get_unit_price([[0, '2.8890']])),
        ('instance:memory-12', 'compute', region, get_unit_price([[0, '4.3330']])),
        ('instance:compute-2', 'compute', region, get_unit_price([[0, '0.3330']])),
        ('instance:compute-4', 'compute', region, get_unit_price([[0, '0.6670']])),
        ('instance:compute-8', 'compute', region, get_unit_price([[0, '1.3330']])),
        ('instance:compute-12', 'compute', region, get_unit_price([[0, '2.0000']])),
        ('ip.floating', 'network', region, get_unit_price([[0, '0.0300']])),
        ('volume.size', 'block_storage', region, get_unit_price([[0, '0.0060']])),
        ('sata.volume.size', 'block_storage', region, get_unit_price([[0, '0.0060']])),
        ('ssd.volume.size', 'block_storage', region, get_unit_price([[0, '0.0200']])),
        ('snapshot.size', 'block_storage', region, get_unit_price([[0, '0.0020']])),
        ('listener', 'network', region, get_unit_price([[0, '0.0010']])),
    ]
    for name, service, region_id, unit_price in products:
        try:
            create_or_update_product(name, service, region_id, unit_price)
        except Exception:
            raise
