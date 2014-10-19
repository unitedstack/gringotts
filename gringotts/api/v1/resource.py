import pecan
import wsme

from pecan import rest
from pecan import request
from wsme import types as wtypes
from wsmeext.pecan import wsexpose

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

        LOG.warn("deleting resources of tenant(%s) in region(%s)" % (project_id, region_name))

        # Ensure snapshots to be deleted before volume
        cinder.delete_snapshots(project_id, region_name=region_name)
        glance.delete_images(project_id, region_name=region_name)
        neutron.delete_fips(project_id, region_name=region_name)
        neutron.delete_routers(project_id, region_name=region_name)
        nova.delete_servers(project_id, region_name=region_name)
        ceilometer.delete_alarms(project_id, region_name=region_name)
        cinder.delete_volumes(project_id, region_name=region_name)
