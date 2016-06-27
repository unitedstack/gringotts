import re
from stevedore import extension
from oslo_config import cfg

from gringotts import constants as const
from gringotts.middleware import base
from gringotts.openstack.common import jsonutils
from gringotts.services import glance


UUID_RE = r"([0-9a-f]{32}|[0-9a-z]{8}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{12})"
API_VERSION = r"(v1|v2)"
RESOURCE_RE = r"(images)"


class SizeItem(base.ProductItem):
    service = const.SERVICE_BLOCKSTORAGE

    def get_product_name(self, body):
        return const.PRODUCT_SNAPSHOT_SIZE

    def get_resource_volume(self, env, body):
        base_image_id = env['HTTP_X_IMAGE_META_PROPERTY_BASE_IMAGE_REF']
        image = glance.image_get(base_image_id, cfg.CONF.billing.region_name)
        return int(image.size) / (1024 ** 3)


class GlanceBillingProtocol(base.BillingProtocol):

    def __init__(self, app, conf):
        super(GlanceBillingProtocol, self).__init__(app, conf)
        self.resource_regex = re.compile(
            r"^/%s/%s/%s([.][^.]+)?$" % (API_VERSION, RESOURCE_RE, UUID_RE), re.UNICODE)
        self.create_resource_regex = re.compile(
            r"^/%s/%s([.][^.]+)?$" % (API_VERSION, RESOURCE_RE), re.UNICODE)
        self.position = 2
        self.resource_regexs = [
            self.resource_regex,
        ]

        self.product_items = extension.ExtensionManager(
            namespace='gringotts.snapshot.product_items',
            invoke_on_load=True,
            invoke_args=(self.gclient,))

    def parse_app_result(self, body, result, user_id, project_id):
        resources = []
        try:
            result = jsonutils.loads(result[0])
            resources.append(base.Resource(
                resource_id=result['image']['id'],
                resource_name=result['image']['name'],
                type=const.RESOURCE_SNAPSHOT,
                status=const.STATE_RUNNING,
                user_id=user_id,
                project_id=project_id))
        except Exception:
            return []
        return resources


def filter_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)

    def bill_filter(app):
        return GlanceBillingProtocol(app, conf)
    return bill_filter
