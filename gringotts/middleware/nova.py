import re
import logging
from stevedore import extension
from oslo_config import cfg

from gringotts import constants as const
from gringotts import exception
from gringotts.middleware import base
from gringotts.openstack.common import jsonutils
from gringotts.openstack.common import timeutils
from gringotts.openstack.common import memorycache
from gringotts.services import nova
from gringotts.services import glance
from gringotts import utils as gringutils

LOG = logging.getLogger(__name__)

UUID_RE = r"([0-9a-f]{32}|[0-9a-z]{8}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{12})"
RESOURCE_RE = r"(os-volumes|os-snapshots|os-floating-ips|os-floating-ips-bulk|images|servers)"


MC = None


def _get_cache():
    global MC
    if MC is None:
        MC = memorycache.get_client()
    return MC


def _make_flavor_key(flavor_id):
    return str("flavor_%s" % flavor_id)


def _make_image_key(image_id):
    return str("image_%s" % image_id)


def _get_flavor(flavor_id):
    cache = _get_cache()
    key = _make_flavor_key(flavor_id)
    flavor = cache.get(key)
    if not flavor:
        try:
            flavor = nova.flavor_get(cfg.CONF.billing.region_name,
                                     flavor_id).to_dict()
        except Exception:
            msg = 'Error to fetch flavor: %s' % flavor_id
            LOG.exception(msg)
            raise exception.GringottsException(message=msg)
        cache.set(key, flavor, 86400)
    return flavor


def _get_image(image_id):
    cache = _get_cache()
    key = _make_image_key(image_id)
    image = cache.get(key)
    if not image:
        image = glance.image_get(image_id,
                                 cfg.CONF.billing.region_name).as_dict()
        if not image:
            msg = 'Error to fetch image: %s' % image_id
            LOG.exception(msg)
            raise exception.GringottsException(message=msg)
        cache.set(key, image, 86400)
    return image


class FlavorItem(base.ProductItem):
    service = const.SERVICE_COMPUTE

    def get_product_name(self, body):
        flavor_id = body['server']['flavorRef']
        flavor = _get_flavor(flavor_id)
        product_name = 'instance:%s' % flavor['name']
        return product_name


class LicenseItem(base.ProductItem):
    service = const.SERVICE_COMPUTE

    def get_product_name(self, body):
        # NOTE(chengkun): if we start instance from volume, there
        # are no License, so we should not use 'imageRef'
        if body['server'].has_key('imageRef'):
            image_id = body['server']['imageRef']
            image = _get_image(image_id)
            product_name = 'license:%s' % image['image_label']
        else:
            product_name = None
        return product_name


class DiskItem(base.ProductItem):
    service = const.SERVICE_BLOCKSTORAGE

    def get_product_name(self, body):
        return const.PRODUCT_VOLUME_SIZE

    def get_resource_volume(self, env, body):
        flavor_id = body['server']['flavorRef']
        flavor = _get_flavor(flavor_id)
        return flavor['disk']


class NovaBillingProtocol(base.BillingProtocol):

    def __init__(self, app, conf):
        super(NovaBillingProtocol, self).__init__(app, conf)
        self.resource_regex = re.compile(
            r"^/%s/%s/%s([.][^.]+)?$" % (UUID_RE, RESOURCE_RE, UUID_RE), re.UNICODE)
        self.create_resource_regex = re.compile(
            r"^/%s/%s([.][^.]+)?$" % (UUID_RE, RESOURCE_RE), re.UNICODE)

        self.server_action_regex = re.compile(
            r"^/%s/(servers)/%s/action([.][^.]+)?$" % (UUID_RE, UUID_RE))
        self.attach_volume_to_server_regex = re.compile(
            r"^/%s/(servers)/%s/os-volume_attachments([.][^.]+)?$" % \
            (UUID_RE, UUID_RE))

        self.position = 2
        self.black_list += [
            self.other_server_actions,
            self.resize_server_action,
            self.attach_volume_to_server_action,
            self.start_server_action,
            self.stop_server_action,
        ]
        self.resource_regexs = [
            self.resource_regex,
            self.server_action_regex,
            self.attach_volume_to_server_regex,
        ]
        self.resize_resource_actions = [
            self.resize_server_action,
        ]
        self.stop_resource_actions = [
            self.stop_server_action,
        ]
        self.start_resource_actions = [
            self.start_server_action,
        ]
        self.product_items = extension.ExtensionManager(
            namespace='gringotts.server.product_items',
            invoke_on_load=True,
            invoke_args=(self.gclient,))

    def other_server_actions(self, method, path_info, body):
        if method == "POST" and \
                self.server_action_regex.search(path_info) and \
                (body.has_key('createImage') or \
                 body.has_key('addFloatingIp') or \
                 body.has_key('reboot') or \
                 body.has_key('rebuild') or \
                 body.has_key('unpause') or \
                 body.has_key('resume') or \
                 body.has_key('unshelve') or \
                 body.has_key('unrescue')):
            return True
        return False

    def start_server_action(self, method, path_info, body):
        if method == "POST" and \
            self.server_action_regex.search(path_info) and \
            (body.has_key('os-start') or \
             body.has_key('unshelve') or \
             body.has_key('unpause')):
            return True
        return False

    def stop_server_action(self, method, path_info, body):
        if method == "POST" and \
            self.server_action_regex.search(path_info) and \
            (body.has_key('os-stop') or \
             body.has_key('shelve') or \
             body.has_key('pause')):
            return True
        return False

    def resize_server_action(self, method, path_info, body):
        if method == "POST" and \
                self.server_action_regex.search(path_info) and \
                (body.has_key('resize') or \
                 body.has_key('localResize')):
            return True
        return False

    def attach_volume_to_server_action(self, method, path_info, body):
        if method == "POST" \
            and self.attach_volume_to_server_regex.search(path_info):
            return True
        return False

    def get_resource_count(self, body):
        count = body['server'].get('max_count') or 1
        if count < 1:
            return False, "max_count must be >= 1"
        if count > 1 and not body['server'].get('return_reservation_id'):
            msg = "must set return_reservation_id to true in body " \
                  "if want to create multiple servers"
            return False, msg
        return True, count

    def parse_app_result(self, body, result, user_id, project_id):
        resources = []
        count = body['server'].get('max_count') or 1
        if count == 1:
            try:
                if body['server'].get('return_reservation_id'):
                    resv_id = jsonutils.loads(result[0])['reservation_id']
                    servers = nova.server_list_by_resv_id(
                        resv_id, region_name=cfg.CONF.billing.region_name)
                    server = servers[0].to_dict()
                else:
                    server = jsonutils.loads(result[0])['server']
                resources.append(base.Resource(
                    resource_id=server['id'],
                    resource_name=body['server']['name'],
                    type=const.RESOURCE_INSTANCE,
                    status=const.STATE_RUNNING,
                    user_id=user_id,
                    project_id=project_id))
            except Exception:
                return []
        else:
            try:
                resv_id = jsonutils.loads(result[0])['reservation_id']
                servers = nova.server_list_by_resv_id(
                    resv_id, region_name=cfg.CONF.billing.region_name)
                for server in servers:
                    server = server.to_dict()
                    resources.append(base.Resource(
                        resource_id=server['id'],
                        resource_name=server['name'],
                        type=const.RESOURCE_INSTANCE,
                        status=const.STATE_RUNNING,
                        user_id=user_id,
                        project_id=project_id))
            except Exception:
                return []
        return resources

    def resize_resource_order(self, env, body, start_response, order_id,
                              resource_id, resource_type):
        new_flavor = body['resize'].get('flavorRef', None)
        if not new_flavor:
            msg = "Must specify the new flavor"
            LOG.exception(msg)
            return False, self._reject_request_500(env, start_response)

        old_flavor = nova.server_get(resource_id).flavor['id']

        if new_flavor == old_flavor:
            return True, None

        region_id = cfg.CONF.billing.region_name

        new_flavor = '%s:%s' % (const.PRODUCT_INSTANCE_TYPE_PREFIX,
                                nova.flavor_get(region_id, new_flavor).name)
        old_flavor = '%s:%s' % (const.PRODUCT_INSTANCE_TYPE_PREFIX,
                                nova.flavor_get(region_id, old_flavor).name)
        service = const.SERVICE_COMPUTE

        try:
            self.gclient.resize_resource_order(order_id,
                                               resource_type=resource_type,
                                               new_flavor=new_flavor,
                                               old_flavor=old_flavor,
                                               service=service,
                                               region_id=region_id)
        except Exception as e:
            msg = "Unable to resize the order: %s" % order_id
            LOG.exception(msg)
            return False, self._reject_request_500(env, start_response)

        return True, None


def filter_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)

    def bill_filter(app):
        return NovaBillingProtocol(app, conf)
    return bill_filter
