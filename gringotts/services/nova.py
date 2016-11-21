import functools
from oslo_config import cfg
import logging as log

from gringotts import utils
from gringotts import constants as const

from novaclient.v2 import client as nova_client
from novaclient.exceptions import NotFound

from gringotts.openstack.common import timeutils

from gringotts.services import keystone as ks_client
from gringotts.services import wrap_exception, register
from gringotts.services import Resource


LOG = log.getLogger(__name__)
register = functools.partial(register,
                             ks_client,
                             service='compute',
                             resource=const.RESOURCE_INSTANCE,
                             stopped_state=const.STATE_STOPPED)


class Server(Resource):
    def to_message(self):
        msg = {
            'event_type': 'compute.instance.create.end.again',
            'payload': {
                'instance_type': self.flavor_name,
                'disk_gb': self.disk_gb,
                'instance_id': self.id,
                'display_name': self.name,
                'user_id': self.user_id,
                'tenant_id': self.project_id,
                'image_name': self.image_name,
                'image_meta': {
                    'base_image_ref': self.image_id
                }
            },
            'timestamp': utils.format_datetime(timeutils.strtime())
        }
        return msg

    def to_env(self):
        return dict(HTTP_X_USER_ID=self.user_id, HTTP_X_PROJECT_ID=self.project_id)

    def to_body(self):
        body = {}
        body['server'] = dict(imageRef=self.image_id, flavorRef=self.flavor_id)
        return body


def get_novaclient(region_name=None):
    ks_cfg = cfg.CONF.keystone_authtoken
    endpoint = ks_client.get_endpoint(region_name, 'compute')
    auth_token = ks_client.get_token()
    auth_url = ks_client.get_auth_url()

    # Actually, there is no need to give any params to novaclient,
    # but it requires parameters.
    c = nova_client.Client(ks_cfg.admin_user,
                           ks_cfg.admin_password,
                           None, # project_id is not required
                           auth_url=auth_url)

    # Give auth_token and management_url directly to avoid authenticate again.
    c.client.auth_token = auth_token
    c.client.management_url = endpoint
    return c


def flavor_list(is_public=True, region_name=None):
    """Get the list of available instance sizes (flavors)."""
    return get_novaclient(region_name=region_name).\
        flavors.list(is_public=is_public)


def flavor_get(region_name, flavor_id):
    return get_novaclient(region_name=region_name).\
        flavors.get(flavor_id)


def image_get(region_name, image_id):
    return get_novaclient(region_name=region_name).\
        images.get(image_id)


@register(mtype='get')
@wrap_exception(exc_type='get')
def server_get(instance_id, region_name=None):
    try:
        server = get_novaclient(region_name).servers.get(instance_id)
    except NotFound:
        return None
    status = utils.transform_status(server.status)
    return Server(id=server.id,
                  name=server.name,
                  status=status,
                  original_status=server.status,
                  resource_type=const.RESOURCE_INSTANCE,
                  flavor=server.flavor)


def server_list_by_resv_id(resv_id, region_name=None, detailed=False):
    search_opts = {'reservation_id': resv_id,
                   'all_tenants': 1}
    return get_novaclient(region_name).servers.list(detailed, search_opts)


@register(mtype='list')
@wrap_exception(exc_type='list')
def server_list(project_id, region_name=None, detailed=True, project_name=None):
    search_opts = {'all_tenants': 1,
                   'project_id': project_id}
    servers = get_novaclient(region_name).servers.list(detailed, search_opts)
    formatted_servers = []
    for server in servers:
        flavor = flavor_get(region_name, server.flavor['id'])
        image = image_get(region_name, server.image['id'])
        created_at = utils.format_datetime(server.created)
        status = utils.transform_status(server.status)
        formatted_servers.append(Server(id=server.id,
                                        name=server.name,
                                        flavor_name=flavor.name,
                                        flavor_id=flavor.id,
                                        disk_gb=getattr(image, "OS-EXT-IMG-SIZE:size") / (1024 * 1024 * 1024),
                                        image_name=image.name,
                                        image_id=image.id,
                                        status=status,
                                        original_status=server.status,
                                        resource_type=const.RESOURCE_INSTANCE,
                                        user_id=server.user_id,
                                        project_id=server.tenant_id,
                                        project_name=project_name,
                                        created_at=created_at))
    return formatted_servers


def server_with_flavor_and_image(server, region_name):
    flavor = flavor_get(region_name, server.flavor_id)
    image = image_get(region_name, server.image_id)


@register(mtype='deletes')
@wrap_exception(exc_type='bulk')
def delete_servers(project_id, region_name=None):
    """Delete all servers that belongs to project_id
    """
    client = get_novaclient(region_name)
    search_opts = {'all_tenants': 1,
                   'project_id': project_id}
    servers = client.servers.list(detailed=False, search_opts=search_opts)
    for server in servers:
        client.servers.delete(server)
        LOG.warn("Delete server: %s" % server.id)


@register(mtype='delete')
@wrap_exception(exc_type='delete')
def delete_server(instance_id, region_name=None):
    client = get_novaclient(region_name)
    client.servers.delete(instance_id)


@register(mtype='stop')
@wrap_exception(exc_type='stop')
def stop_server(instance_id, region_name=None):
    client = get_novaclient(region_name)
    client.servers.stop(instance_id)
    return True


@wrap_exception(exc_type='put')
def quota_update(project_id, user_id=None, region_name=None, **kwargs):
    """
    kwargs = {"instances": 10,
              "cores": 20,
              "ram": 1024,
              "user_id": "xxxxxxxxx"}
    """
    client = get_novaclient(region_name)
    if user_id:
        kwargs.update(user_id=user_id)
    client.quotas.update(project_id, **kwargs)


@wrap_exception(exc_type='get')
def quota_get(project_id, user_id=None, region_name=None):
    """
    {u'cores': {u'in_use': 0, u'limit': 70, u'reserved': 0},
     u'instances': {u'in_use': 0, u'limit': 10, u'reserved': 0},
     u'ram': {u'in_use': 0, u'limit': 204800, u'reserved': 0},
    """
    client = get_novaclient(region_name)
    return client.quotas.get(project_id, user_id=user_id, usages=True)._info
