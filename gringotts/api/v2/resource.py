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
from gringotts import services
from gringotts import context
from gringotts.openstack.common import log


LOG = log.getLogger(__name__)


class ResourcesController(rest.RestController):
    """Operations on resources."""
    @wsexpose(None, wtypes.text, wtypes.text)
    def delete(self, project_id, region_name=None):
        """Delete all resources in specified region that belongs to a tenant

        :param region_name: when in multiple region, this parameter must be specified.
        """
        context.require_admin_context(request.context)
        regions = [region_name] if region_name else cfg.CONF.regions

        DELETE_METHODS = services.RESOURCE_DELETE_METHOD

        for region_name in regions:
            LOG.warn("deleting resources of tenant(%s) in region(%s)" % (project_id, region_name))
            for method in DELETE_METHODS:
                method(project_id, region_name=region_name)

    @wsexpose([models.Resource], wtypes.text, wtypes.text)
    def get_all(self, project_id, region_name=None):
        """ Get all resources of specified project_id in the region specified by
        the region_name or the regions in conf file."""
        project_id = acl.get_limited_to_project(request.headers, 'uos_staff') or project_id
        if project_id is None:
            project_id = request.headers.get('X-Project-Id')

        LIST_METHODS = services.RESOURCE_LIST_METHOD
        result = []
        regions = [region_name] if region_name else cfg.CONF.regions

        for method, _region_name in itertools.product(LIST_METHODS, regions):
            resources = method(project_id, region_name=_region_name)
            for resource in resources:
                result.append(models.Resource(region_name=_region_name,
                                              resource_id=resource.id,
                                              resource_name=resource.name,
                                              resource_type=resource.resource_type))
        return result

    @wsexpose(None, wtypes.text)
    def get(self, resource_id):
        """ Just for testing resource_get method."""
        GET_METHODS = services.RESOURCE_GET_MAP.values()
        for method in GET_METHODS:
            method(resource_id)
