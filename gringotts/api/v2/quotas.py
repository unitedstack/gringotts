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
    """Operations on resources."""

    @wsexpose(None, body=models.QuotaBody)
    def put(self, data):
        """ Get all resources of specified project_id in all regions."""
        from gringotts.services import cinder
        from gringotts.services import neutron
        from gringotts.services import nova
        from gringotts.services import trove

        project_id = acl.get_limited_to_project(request.headers, 'uos_support_staff')
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

        if data.quotas != wtypes.Unset:
            trove.quota_update(data.project_id, **data.quotas.as_dict())

    @wsexpose(models.Quota, wtypes.text, wtypes.text, wtypes.text)
    def get(self, project_id=None, user_id=None, region_name=None):
        """Get quota of specified project in specified region."""
        from gringotts.services import cinder
        from gringotts.services import neutron
        from gringotts.services import nova
        from gringotts.services import trove

        _project_id = acl.get_limited_to_project(request.headers, 'uos_support_staff')
        if _project_id:
            raise exception.NotAuthorized

        if not project_id or not region_name:
            raise exception.Invalid

        nq = nova.quota_get(project_id, user_id, region_name)
        compute_quota = None
        if nq:
            compute_quota = models.ComputeQuota(
                instances=models.QuotaItem(limit=nq['instances']['limit'],
                                           used=nq['instances']['in_use']),
                cores=models.QuotaItem(limit=nq['cores']['limit'],
                                       used=nq['cores']['in_use']),
                ram=models.QuotaItem(limit=nq['ram']['limit'],
                                     used=nq['ram']['in_use']),
                key_pairs=models.QuotaItem(limit=nq['key_pairs']['limit'],
                                           used=nq['key_pairs']['in_use'])
            )

        cq = cinder.quota_get(project_id, user_id, region_name)
        volume_types = cinder.type_list(project_id, region_name)
        volume_quotas = []
        if cq:
            for vtype in volume_types:
                volume_quota = models.VolumeQuota(
                    volume_type=vtype.name,
                    gigabytes=models.QuotaItem(limit=cq['gigabytes_%s' % vtype.name]['limit'],
                                               used=cq['gigabytes_%s' % vtype.name]['in_use']),
                    snapshots=models.QuotaItem(limit=cq['snapshots_%s' % vtype.name]['limit'],
                                               used=cq['snapshots_%s' % vtype.name]['in_use']),
                    volumes=models.QuotaItem(limit=cq['volumes_%s' % vtype.name]['limit'],
                                             used=cq['volumes_%s' % vtype.name]['in_use']),
                )
                volume_quotas.append(volume_quota)

        nnq = neutron.quota_get(project_id, region_name)
        network_quota = None
        if nnq:
            network_quota = models.NetworkQuota(
                floatingip = models.QuotaItem(limit=nnq['floatingip']['limit'],
                                              used=nnq['floatingip']['in_use']),
                listener = models.QuotaItem(limit=nnq['listener']['limit'],
                                            used=nnq['listener']['in_use']),
                loadbalancer = models.QuotaItem(limit=nnq['loadbalancer']['limit'],
                                                used=nnq['loadbalancer']['in_use']),
                network = models.QuotaItem(limit=nnq['network']['limit'],
                                           used=nnq['network']['in_use']),
                pool = models.QuotaItem(limit=nnq['pool']['limit'],
                                        used=nnq['pool']['in_use']),
                router = models.QuotaItem(limit=nnq['router']['limit'],
                                          used=nnq['router']['in_use']),
                subnet = models.QuotaItem(limit=nnq['subnet']['limit'],
                                          used=nnq['subnet']['in_use']),
                security_group = models.QuotaItem(limit=nnq['security_group']['limit'],
                                                  used=nnq['security_group']['in_use']),
                portforwardings = models.QuotaItem(limit=nnq['portforwardings']['limit'],
                                                   used=nnq['portforwardings']['in_use']),
            )

        tq = trove.quota_get(project_id, region_name)
        database_quota = None
        if tq:
            database_quota = models.TroveQuota(
                instances = models.QuotaItem(limit=tq['instances']['limit'],
                                             used=tq['instances']['in_use']),
                backups = models.QuotaItem(limit=tq['backups']['limit'],
                                           used=tq['backups']['in_use']),
                volumes = models.QuotaItem(limit=tq['volumes']['limit'],
                                           used=tq['volumes']['in_use']),
            )

        return models.Quota(project_id=project_id,
                            user_id=user_id,
                            region_name=region_name,
                            compute=compute_quota,
                            volume=volume_quotas,
                            network=network_quota,
                            quotas=database_quota)
