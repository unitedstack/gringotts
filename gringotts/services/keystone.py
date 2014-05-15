from oslo.config import cfg
from keystoneclient.v3 import client

from gringotts import exception
from gringotts.openstack.common import memorycache
from gringotts.openstack.common import log


LOG = log.getLogger(__name__)

CACHE_SECONDS = 60 * 60 * 24
MC = None


def _get_cache():
    global MC
    if MC is None:
        MC = memorycache.get_client()
    return MC


def force_v3_api(url):
    if url is None:
        return url
    if url.endswith('/v2.0'):
        return url.replace('/v2.0', '/v3')
    return url


ks_client = None


def get_ks_client():
    global ks_client
    if ks_client is None:
        os_cfg = cfg.CONF.service_credentials
        ks_client = client.Client(user_domain_name=os_cfg.user_domain_name,
                                  username=os_cfg.os_username,
                                  password=os_cfg.os_password,
                                  project_domain_name=os_cfg.project_domain_name,
                                  project_name=os_cfg.os_tenant_name,
                                  auth_url=os_cfg.os_auth_url)
        ks_client.management_url = force_v3_api(ks_client.management_url)
    return ks_client


def _get_catalog():

    # Read from cache first
    cache = _get_cache()
    key = 'gring-keystone-catalog'
    catalog = cache.get(key)
    if catalog:
        return catalog

    try:
        endpoints = get_ks_client().endpoints.list()
        services = get_ks_client().services.list()
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

    cache.set(key, catalog, CACHE_SECONDS)

    return catalog


def get_admin_tenant_id():
    return get_ks_client().project_id


def get_admin_user_id():
    return get_ks_client().user_id


def get_endpoint(region_name, service_type, endpoint_type=None, project_id=None):
    """
    Keystoneclient(havana) doesn't support multiple regions,
    so we should implement it by ourselves.
    Keystoneclient(icehouse) can do the same thing like this:
    get_ks_client().service_catalog.url_for(service_type=xxx,
                                            endpoint_type=yyy,
                                            region_name=zzz)
    """
    catalog = _get_catalog()

    if not catalog:
        raise exception.EmptyCatalog()

    if not endpoint_type:
        endpoint_type = cfg.CONF.service_credentials.os_endpoint_type

    endpoint_type = endpoint_type.rstrip('URL')

    if not project_id:
        project_id = get_admin_tenant_id()

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

    raise exception.EndpointNotFound(endpoint_type=endpoint_type,
                                     service_type=service_type)


def get_token():
    return get_ks_client().auth_token


def _get_owed_role_id():
    cache = _get_cache()
    key = "gring-owed-role-id"
    role_id = cache.get(key)
    if role_id:
        return role_id
    roles = get_ks_client().roles.list()
    for role in roles:
        if role.name == 'ower':
            role_id = role.id
            break
    if not role_id:
        role_id = get_ks_client().roles.create('ower').id
    cache.set(key, role_id, CACHE_SECONDS * 30)
    return role_id


def grant_owed_role(user_id, project_id):
    role_id = _get_owed_role_id()
    get_ks_client().roles.grant(role_id, user=user_id, project=project_id)


def revoke_owed_role(user_id, project_id):
    role_id = _get_owed_role_id()
    get_ks_client().roles.revoke(role_id, user=user_id, project=project_id)


def get_user_list():
    return get_ks_client().users.list()


def get_project_list():
    return get_ks_client().projects.list()


def get_role_list(user=None, group=None, domain=None, project=None):
    """Get role list of particular user on particular project by
    given the user and project parameters.

    NOTE: Role is granted to user on particular project
    """
    return get_ks_client().roles.list(user=user,
                                      group=group,
                                      domain=domain,
                                      project=project)
