import functools
import time
from oslo_config import cfg
import logging as log

from gringotts import utils
from gringotts import constants as const
from gringotts.services import wrap_exception,register
from gringotts.services import Resource
from cinderclient.v1 import client as cinder_client
from cinderclient.exceptions import NotFound
from gringotts.services import keystone as ks_client
from gringotts.openstack.common import uuidutils
from gringotts.openstack.common import timeutils


LOG = log.getLogger(__name__)
register = functools.partial(register,
                             ks_client,
                             service='volume',
                             resource=const.RESOURCE_VOLUME,
                             stopped_state=const.STATE_RUNNING)

class Volume(Resource):
    def to_message(self):
        msg = {
            'event_type': 'volume.create.end.again',
            'payload': {
                'volume_id': self.id,
                'display_name': self.name,
                'size': self.size,
                'volume_type': self.type,
                'user_id': self.user_id,
                'tenant_id': self.project_id
            },
            'timestamp': utils.format_datetime(timeutils.strtime())
        }
        return msg

    def to_env(self):
        """
        :returns: TODO

        """
        return dict(HTTP_X_USER_ID=self.user_id, HTTP_X_PROJECT_ID=self.project_id)

    def to_body(self):
        body = {}
        body[self.resource_type] = dict(volume_type=self.type, size=self.size)
        return body


class Snapshot(Resource):
    def to_message(self):
        msg = {
            'event_type': 'snapshot.create.end.again',
            'payload': {
                'snapshot_id': self.id,
                'display_name': self.name,
                'volume_size': self.size,
                'user_id': self.user_id,
                'tenant_id': self.project_id
            },
            'timestamp': utils.format_datetime(timeutils.strtime())
        }
        return msg

    def to_env(self):
        return dict(HTTP_X_USER_ID=self.user_id, HTTP_X_PROJECT_ID=self.project_id)

    def to_body(self):
        body = {}
        body[self.resource_type] = dict(snapshot_id=self.id)
        return body


def get_cinderclient(region_name=None):
    ks_cfg = cfg.CONF.keystone_authtoken
    endpoint = ks_client.get_endpoint(region_name, 'volume')
    auth_token = ks_client.get_token()
    auth_url = ks_client.get_auth_url()
    c = cinder_client.Client(ks_cfg.admin_user,
                             ks_cfg.admin_password,
                             None,
                             auth_url=auth_url)
    c.client.auth_token = auth_token
    c.client.management_url = endpoint
    return c


@register(mtype='get')
@wrap_exception(exc_type='get')
def volume_get(volume_id, region_name=None):
    c_client = get_cinderclient(region_name)
    try:
        volume = c_client.volumes.get(volume_id)
    except NotFound:
        return None
    status = utils.transform_status(volume.status)
    return Volume(id=volume.id,
                  name=volume.display_name,
                  status=status,
                  original_status=volume.status,
                  resource_type=const.RESOURCE_VOLUME,
                  attachments=volume.attachments,
                  size=volume.size)


@register(resource=const.RESOURCE_SNAPSHOT, mtype='get')
@wrap_exception(exc_type='get')
def snapshot_get(snapshot_id, region_name=None):
    c_client = get_cinderclient(region_name)
    try:
        sp = c_client.volume_snapshots.get(snapshot_id)
    except NotFound:
        return None
    status = utils.transform_status(sp.status)
    return Snapshot(id=sp.id,
                    name=sp.display_name,
                    size=sp.size,
                    status=status,
                    original_status=sp.status,
                    resource_type=const.RESOURCE_SNAPSHOT)


@wrap_exception(exc_type='get')
def volume_type_get(volume_type, region_name=None):
    if not uuidutils.is_uuid_like(volume_type):
        return volume_type

    c_client = get_cinderclient(region_name)
    try:
        vt = c_client.volume_types.get(volume_type)
    except NotFound:
        return None
    return vt.name


@register(mtype='list')
@wrap_exception(exc_type='list')
def volume_list(project_id, region_name=None, detailed=True, project_name=None):
    """To see all volumes in the cloud as admin.
    """
    c_client = get_cinderclient(region_name)
    search_opts = {'all_tenants': 1,
                   'project_id': project_id}
    if c_client is None:
        return []
    volumes = c_client.volumes.list(detailed, search_opts=search_opts)
    formatted_volumes = []
    for volume in volumes:
        created_at = utils.format_datetime(volume.created_at)
        status = utils.transform_status(volume.status)
        formatted_volumes.append(Volume(id=volume.id,
                                        name=volume.display_name,
                                        size=volume.size,
                                        status=status,
                                        type=volume.volume_type,
                                        original_status=volume.status,
                                        resource_type=const.RESOURCE_VOLUME,
                                        user_id = None,
                                        project_id = project_id,
                                        project_name=project_name,
                                        attachments=volume.attachments,
                                        created_at=created_at))
    return formatted_volumes


@register(mtype='list')
@wrap_exception(exc_type='list')
def snapshot_list(project_id, region_name=None, detailed=True, project_name=None):
    """To see all snapshots in the cloud as admin
    """
    c_client = get_cinderclient(region_name)
    search_opts = {'all_tenants': 1,
                   'project_id': project_id}
    if c_client is None:
        return []
    snapshots = c_client.volume_snapshots.list(detailed, search_opts=search_opts)
    formatted_snap = []
    for sp in snapshots:
        created_at = utils.format_datetime(sp.created_at)
        status = utils.transform_status(sp.status)
        formatted_snap.append(Snapshot(id=sp.id,
                                       name=sp.display_name,
                                       size=sp.size,
                                       status=status,
                                       original_status=sp.status,
                                       resource_type=const.RESOURCE_SNAPSHOT,
                                       user_id=None,
                                       project_id=project_id,
                                       project_name=project_name,
                                       created_at=created_at,
                                       volume_id=sp.volume_id))
    return formatted_snap


@register(mtype='deletes')
@wrap_exception(exc_type='bulk')
def delete_volumes(project_id, region_name=None):
    """Delete all volumes that belong to project_id
    """
    client = get_cinderclient(region_name)
    search_opts = {'all_tenants': 1,
                   'project_id': project_id}
    volumes = client.volumes.list(detailed=False, search_opts=search_opts)

    # Should delete the snapshots first
    delete_snapshots(project_id, region_name)

    # Force delete or detach and then delete
    for volume in volumes:
        # try to delete attachments
        for attachment in volume.attachments:
            try:
                client.volumes.detach(volume, attachment['attachment_id'])
            except Exception:
                pass
        time.sleep(1)
        client.volumes.delete(volume)
        LOG.warn("Delete volume: %s" % volume.id)


@register(mtype='deletes')
@wrap_exception(exc_type='bulk')
def delete_snapshots(project_id, region_name=None, volume_id=None):
    """Delete all snapshots that belong to project_id
    """
    client = get_cinderclient(region_name)
    search_opts = {'all_tenants': 1,
                   'project_id': project_id}
    if volume_id:
        search_opts.update(volume_id=volume_id)
    snaps = client.volume_snapshots.list(detailed=False,
                                         search_opts=search_opts)
    for snap in snaps:
        try:
            client.volume_snapshots.delete(snap)
            LOG.warn("Delete snapshot: %s" % snap.id)
        except Exception:
            pass


@register(mtype='delete')
@wrap_exception(exc_type='delete')
def delete_volume(volume_id, region_name=None):
    client = get_cinderclient(region_name)

    # delete all snapshots first that rely on this volume
    search_opts = {'all_tenants': 1,
                   'volume_id': volume_id}
    snaps = client.volume_snapshots.list(detailed=False,
                                         search_opts=search_opts)
    for snap in snaps:
        try:
            client.volume_snapshots.delete(snap)
        except Exception:
            pass

    # detach volume from instance
    volume = volume_get(volume_id, region_name=region_name)
    for attachment in volume.attachments:
        try:
            client.volumes.detach(volume_id, attachment['attachment_id'])
        except Exception:
            pass

    # wait 10 seconds to delete this volume
    time.sleep(10)
    client.volumes.delete(volume_id)


@register(mtype='stop')
@wrap_exception(exc_type='stop')
def stop_volume(volume_id, region_name=None):
    return True


@register(resource=const.RESOURCE_SNAPSHOT, mtype='delete')
@wrap_exception(exc_type='delete')
def delete_snapshot(snap_id, region_name=None):
    client = get_cinderclient(region_name)
    client.volume_snapshots.delete(snap_id)


@register(resource=const.RESOURCE_SNAPSHOT, mtype='stop')
@wrap_exception(exc_type='stop')
def stop_snapshot(snap_id, region_id=None):
    return True


@wrap_exception(exc_type='put')
def quota_update(project_id, user_id=None, region_name=None, **kwargs):
    """
    kwargs = {"volume_type": "ssd",
              "volumes": 10,
              "snapshots": 20,
              "gigabytes": 1024}
    """
    try:
        volume_type = kwargs.pop('volume_type')
    except KeyError:
        volume_type = None

    client = get_cinderclient(region_name)
    old_quota = client.quotas.get(project_id)._info

    body = {}
    for k, v in kwargs.iteritems():
        k_x = "%s_%s" % (k, volume_type) if volume_type else k
        body[k_x] = v

        if volume_type:
            total = 0
            prefix = "%s_" % k
            for ko, vo in old_quota.iteritems():
                if ko.startswith(prefix) and ko != k_x:
                    total += vo
            body[k] = v + total
    client.quotas.update(project_id, **body)


@wrap_exception(exc_type='get')
def quota_get(project_id, user_id=None, region_name=None):
    """
    {u'gigabytes': {u'in_use': 0, u'limit': 999, u'reserved': 0},
     u'gigabytes_sata': {u'in_use': 0, u'limit': -1, u'reserved': 0},
     u'gigabytes_ssd': {u'in_use': 0, u'limit': 1000, u'reserved': 0},
     u'snapshots': {u'in_use': 0, u'limit': 32, u'reserved': 0},
     u'snapshots_sata': {u'in_use': 0, u'limit': -1, u'reserved': 0},
     u'snapshots_ssd': {u'in_use': 0, u'limit': 33, u'reserved': 0},
     u'volumes': {u'in_use': 0, u'limit': 40, u'reserved': 0},
     u'volumes_sata': {u'in_use': 0, u'limit': 20, u'reserved': 0},
     u'volumes_ssd': {u'in_use': 0, u'limit': 20, u'reserved': 0}}
    """
    client = get_cinderclient(region_name)
    return client.quotas.get(project_id, usage=True)._info


@wrap_exception(exc_type='list')
def type_list(project_id, region_name=None):
    client = get_cinderclient(region_name)
    return client.volume_types.list()
