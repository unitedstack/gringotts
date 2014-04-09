from oslo.config import cfg

from gringotts import utils
from gringotts import constants as const

from gringotts.services import wrap_exception
from gringotts.services import Resource
from gringotts.services import keystone as ks_client
from neutronclient.v2_0 import client as neutron_client


class FloatingIp(Resource):
    def to_message(self):
        msg = {
            'event_type': 'floatingip.create.end.again',
            'payload': {
                'floatingip': {
                    'id': self.id,
                    'uos:name': self.name,
                    'rate_limit': self.size,
                    'tenant_id': self.project_id
                }
            },
           'timestamp': self.created_at
        }
        return msg


class Router(Resource):
    def to_message(self):
        msg = {
            'event_type': 'router.create.end.again',
            'payload': {
                'router': {
                    'id': self.id,
                    'name': self.name,
                    'tenant_id': self.project_id
                }
            },
            'timestamp': self.created_at
        }
        return msg


def get_neutronclient(region_name=None):
    endpoint = ks_client.get_endpoint(region_name, 'network')
    auth_token = ks_client.get_token()
    c = neutron_client.Client(token=auth_token,
                              endpoint_url=endpoint)
    return c


def subnet_list(project_id, region_name=None):
    client = get_neutronclient(region_name)
    subnets = client.list_subnets(tenant_id=project_id).get('subnets')
    return subnets


def port_list(project_id, region_name=None, device_id=None):
    client = get_neutronclient(region_name)
    ports = client.list_ports(tenant_id=project_id,
                              device_id=device_id).get('ports')
    return ports


def floatingip_list(project_id, region_name=None):
    client = get_neutronclient(region_name)
    if project_id:
        fips = client.list_floatingips(tenant_id=project_id).get('floatingips')
    else:
        fips = client.list_floatingips().get('floatingips')
    formatted_fips = []
    for fip in fips:
        created_at = utils.format_datetime(fip['created_at'])
        status = utils.transform_status(fip['status'])
        formatted_fips.append(FloatingIp(id=fip['id'],
                                         name=fip['uos:name'],
                                         size=fip['rate_limit'],
                                         project_id=fip['tenant_id'],
                                         resource_type=const.RESOURCE_FLOATINGIP,
                                         status=status,
                                         created_at=created_at))
    return formatted_fips


def router_list(project_id, region_name=None):
    client = get_neutronclient(region_name)
    if project_id:
        routers = client.list_routers(tenant_id=project_id).get('routers')
    else:
        routers = client.list_routers().get('routers')
    formatted_routers = []
    for router in routers:
        created_at = utils.format_datetime(router['created_at'])
        status = utils.transform_status(router['status'])
        formatted_routers.append(Router(id=router['id'],
                                        name=router['name'],
                                        project_id=router['tenant_id'],
                                        resource_type=const.RESOURCE_ROUTER,
                                        status=status,
                                        created_at=created_at))
    return formatted_routers


@wrap_exception(exc_type='bulk')
def delete_fips(project_id, region_name=None):
    client = get_neutronclient(region_name)

    # Get floating ips
    fips = client.list_floatingips(tenant_id=project_id)
    fips = fips.get('floatingips')

    # Disassociate these floating ips
    update_dict = {'port_id': None}
    for fip in fips:
        client.update_floatingip(fip['id'],
                                 {'floatingip': update_dict})

    # Release these floating ips
    for fip in fips:
        client.delete_floatingip(fip['id'])


@wrap_exception(exc_type='bulk')
def delete_routers(project_id, region_name=None):
    client = get_neutronclient(region_name)

    routers = client.list_routers(tenant_id=project_id).get('routers')
    for router in routers:
        # Remove gateway
        client.remove_gateway_router(router['id'])

        # Get interfaces of this router
        ports = client.list_ports(tenant_id=project_id,
                                  device_id=router['id']).get('ports')

        # Clear these interfaces from this router
        body = {}
        for port in ports:
            body['port_id'] = port['id']
            client.remove_interface_router(router['id'], body)

        # And then delete this router
        client.delete_router(router['id'])


@wrap_exception()
def delete_fip(fip_id, region_name=None):
    client = get_neutronclient(region_name)
    update_dict = {'port_id': None}
    client.update_floatingip(fip_id,
                             {'floatingip': update_dict})
    client.delete_floatingip(fip_id)


@wrap_exception()
def stop_fip(fip_id, region_name=None):
    client = get_neutronclient(region_name)
    update_dict = {'port_id': None}
    client.update_floatingip(fip_id,
                             {'floatingip': update_dict})
    client.delete_floatingip(fip_id)
    return False


@wrap_exception()
def delete_router(router_id, region_name=None):
    client = get_neutronclient(region_name)

    # Remove gateway
    client.remove_gateway_router(router_id)

    # Get interfaces of this router
    ports = client.list_ports(device_id=router_id).get('ports')

    # Clear these interfaces from this router
    body = {}
    for port in ports:
        body['port_id'] = port['id']
        client.remove_interface_router(router_id, body)

    # And then delete this router
    client.delete_router(router_id)

@wrap_exception()
def stop_router(router_id, region_name=None):
    return True
