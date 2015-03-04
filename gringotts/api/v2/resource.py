import pecan
import wsme
import itertools

from oslo.config import cfg

from pecan import rest
from pecan import request
from wsme import types as wtypes
from wsmeext.pecan import wsexpose

from gringotts.api import acl
from gringotts.api.v2 import models
from gringotts import context
from gringotts.openstack.common import log


LOG = log.getLogger(__name__)


class ResourcesController(rest.RestController):
    """Operations on resources
    """
    @wsexpose(None, wtypes.text, wtypes.text)
    def delete(self, project_id, region_name=None):
        """Delete all resources in specified region that belongs to a tenant

        :param region_name: when in multiple region, this parameter must be specified.
        """
        context.require_admin_context(request.context)

        from gringotts.services import cinder
        from gringotts.services import glance
        from gringotts.services import neutron
        from gringotts.services import nova
        from gringotts.services import ceilometer
        from gringotts.services import manila

        regions = [region_name] if region_name else cfg.CONF.regions

        for region_name in regions:
            LOG.warn("deleting resources of tenant(%s) in region(%s)" % (project_id, region_name))

            # Ensure snapshots to be deleted before volume
            cinder.delete_snapshots(project_id, region_name=region_name)
            glance.delete_images(project_id, region_name=region_name)
            neutron.delete_fips(project_id, region_name=region_name)
            neutron.delete_routers(project_id, region_name=region_name)
            neutron.delete_networks(project_id, region_name=region_name)
            neutron.delete_listeners(project_id, region_name=region_name)
            nova.delete_servers(project_id, region_name=region_name)
            ceilometer.delete_alarms(project_id, region_name=region_name)
            cinder.delete_volumes(project_id, region_name=region_name)
            manila.delete_shares(project_id, region_name=region_name)

    @wsexpose([models.Resource], wtypes.text, wtypes.text)
    def get_all(self, project_id, region_name=None):
        """ Get all resources of specified project_id in all regions
        """
        from gringotts.services import cinder
        from gringotts.services import glance
        from gringotts.services import neutron
        from gringotts.services import nova
        from gringotts.services import ceilometer
        from gringotts.services import manila

        project_id = acl.get_limited_to_project(request.headers) or project_id
        if project_id is None:
            project_id = request.headers.get('X-Project-Id')

        LIST_METHOD = [cinder.volume_list, cinder.snapshot_list,
                       glance.image_list,
                       neutron.network_list, neutron.router_list,
                       neutron.floatingip_list, neutron.listener_list,
                       nova.server_list,
                       ceilometer.alarm_list,
                       manila.share_list]

        result = []
        regions = [region_name] if region_name else cfg.CONF.regions

        for method, _region_name in itertools.product(LIST_METHOD, regions):
            resources = method(project_id, region_name=_region_name)
            for resource in resources:
                result.append(models.Resource(region_name=_region_name,
                                              resource_id=resource.id,
                                              resource_name=resource.name,
                                              resource_type=resource.resource_type))
        return result
