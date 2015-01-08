import pecan
import wsme
import itertools

from oslo.config import cfg

from pecan import rest
from pecan import request
from wsme import types as wtypes
from wsmeext.pecan import wsexpose

from gringotts import exception
from gringotts.api import acl
from gringotts.api.v2 import models
from gringotts import context
from gringotts.openstack.common import log


LOG = log.getLogger(__name__)


class QuotasController(rest.RestController):
    """Operations on resources
    """

    @wsexpose(None, body=models.Quota)
    def put(self, data):
        """ Get all resources of specified project_id in all regions
        """
        from gringotts.services import cinder
        from gringotts.services import neutron
        from gringotts.services import nova

        project_id = acl.get_limited_to_project(request.headers)
        if project_id:
            raise exception.NotAuthorized

        if data.project_id == wtypes.Unset or data.region_name == wtypes.Unset:
            raise exception.InvalidQuotaParameter

        if data.user_id == wtypes.Unset:
            data.user_id = None

        if data.compute != wtypes.Unset:
            nova.quota_update(data.project_id, data.user_id,
                              region_name=data.region_name,
                              **data.compute.as_dict())
        if data.network != wtypes.Unset:
            neutron.quota_update(data.project_id, region_name=data.region_name,
                                 **data.network.as_dict())

        if data.volume != wtypes.Unset:
            for quota_body in data.volume:
                cinder.quota_update(data.project_id, region_name=data.region_name,
                                    **quota_body.as_dict())
