from oslo.config import cfg
import  glanceclient

from gringotts import utils
from gringotts import constants as const

from gringotts.services import keystone as ks_client
from gringotts.services import wrap_exception
from gringotts.services import Resource


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
            'timestamp': self.created_at
        }
        return msg

def get_glanceclient(region_name=None):
    endpoint = ks_client.get_endpoint(region_name, 'image')
    auth_token = ks_client.get_token()
    return glanceclient.Client('1', endpoint, token=auth_token)


def image_list(project_id, region_name=None):
    images = get_glanceclient(region_name).images.list(owner=project_id)
    formatted_images = []
    for image in images:
        created_at = utils.format_datetime(image.created_at)
        status = utils.transform_status(image.status)
        formatted_images.append(Image(id=image.id,
                                      name=image.name,
                                      size=image.size,
                                      status=status,
                                      original_status=image.status,
                                      resource_type=const.RESOURCE_IMAGE,
                                      project_id=project_id,
                                      created_at=created_at))
    return formatted_images


@wrap_exception(exc_type='bulk')
def delete_images(project_id, region_name=None):
    client = get_glanceclient(region_name)
    images = client.images.list(owner=project_id)
    for image in images:
        client.images.delete(image)


@wrap_exception()
def delete_image(image_id, region_name=None):
    client = get_glanceclient(region_name)
    client.images.delete(image_id)


@wrap_exception()
def stop_image(image_id, region_name):
    return True
