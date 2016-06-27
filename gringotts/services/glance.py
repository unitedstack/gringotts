import functools
import logging as log

from oslo_config import cfg
import  glanceclient
from glanceclient.exc import NotFound,HTTPNotFound

from gringotts import utils
from gringotts import constants as const

from gringotts.openstack.common import timeutils
from gringotts.services import keystone as ks_client
from gringotts.services import wrap_exception,register
from gringotts.services import Resource


LOG = log.getLogger(__name__)
register = functools.partial(register,
                             ks_client,
                             service='image',
                             resource=const.RESOURCE_IMAGE,
                             stopped_state=const.STATE_RUNNING)


class Image(Resource):
    def to_message(self):
        msg = {
            'event_type': 'image.activate.again',
            'payload': {
                'id': self.id,
                'name': self.name,
                'size': self.size,
                'owner': self.project_id,
            },
            'timestamp': utils.format_datetime(timeutils.strtime())
        }
        return msg

def get_glanceclient(region_name=None):
    endpoint = ks_client.get_endpoint(region_name, 'image')
    if endpoint[-1] != '/':
        endpoint += '/'
    auth_token = ks_client.get_token()
    return glanceclient.Client('2', endpoint, token=auth_token)


@register(mtype='get')
@wrap_exception(exc_type='get')
def image_get(image_id, region_name=None):
    try:
        image = get_glanceclient(region_name).images.get(image_id)
    except HTTPNotFound:
        return None
    except NotFound:
        return None
    status = utils.transform_status(image.status)
    return Image(id=image.id,
                 name=image.name,
                 image_label=image.get('image_label', 'default').lower(),
                 status=status,
                 original_status=image.status,
                 resource_type=const.RESOURCE_IMAGE,
                 size=image.size)


@register(mtype='list')
@wrap_exception(exc_type='list')
def image_list(project_id, region_name=None, project_name=None):
    filters = {'owner': project_id}
    images = get_glanceclient(region_name).images.list(filters=filters)
    formatted_images = []
    for image in images:
        created_at = utils.format_datetime(image.created_at)
        status = utils.transform_status(image.status)
        formatted_images.append(Image(id=image.id,
                                      name=getattr(image, 'name', None),
                                      size=getattr(image, 'size', 0),
                                      status=status,
                                      original_status=image.status,
                                      resource_type=const.RESOURCE_IMAGE,
                                      project_id=project_id,
                                      project_name=project_name,
                                      created_at=created_at))
    return formatted_images


@register(mtype='deletes')
@wrap_exception(exc_type='bulk')
def delete_images(project_id, region_name=None):
    client = get_glanceclient(region_name)
    filters = {'owner': project_id}
    images = client.images.list(filters=filters)
    for image in images:
        client.images.delete(image.id)
        LOG.warn("Delete image: %s" % image.id)


@register(mtype='delete')
@wrap_exception(exc_type='delete')
def delete_image(image_id, region_name=None):
    client = get_glanceclient(region_name)
    client.images.delete(image_id)


@register(mtype='stop')
@wrap_exception(exc_type='stop')
def stop_image(image_id, region_name):
    return True
