import logging
import re
from stevedore import extension
from oslo_config import cfg

from gringotts import constants as const
from gringotts.middleware import base
from gringotts.openstack.common import jsonutils
from gringotts.services import cinder


LOG = logging.getLogger(__name__)

UUID_RE = r"([0-9a-f]{32}|[0-9a-z]{8}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{12})"
RESOURCE_RE = r"(volumes|snapshots)"


class SizeItem(base.ProductItem):
    service = const.SERVICE_BLOCKSTORAGE

    def get_product_name(self, body):
        if 'volume' in body:
            if body['volume'].get('volume_type') == 'sata':
                return const.PRODUCT_SATA_VOLUME_SIZE
            elif body['volume'].get('volume_type') == 'ssd':
                return const.PRODUCT_SSD_VOLUME_SIZE
            else:
                return const.PRODUCT_VOLUME_SIZE
        elif 'snapshot' in body:
            return const.PRODUCT_SNAPSHOT_SIZE

    def get_resource_volume(self, env, body):
        if 'volume' in body:
            return body['volume']['size']
        elif 'snapshot' in body:
            volume = cinder.volume_get(body['snapshot']['volume_id'],
                                       cfg.CONF.billing.region_name)
            return volume.size


class CinderBillingProtocol(base.BillingProtocol):

    def __init__(self, app, conf):
        super(CinderBillingProtocol, self).__init__(app, conf)
        self.resource_regex = re.compile(
            r"^/%s/%s/%s([.][^.]+)?$" % (UUID_RE, RESOURCE_RE, UUID_RE), re.UNICODE)
        self.create_resource_regex = re.compile(
            r"^/%s/%s([.][^.]+)?$" % (UUID_RE, RESOURCE_RE), re.UNICODE)
        self.volume_action_regex = re.compile(
            r"^/%s/(volumes)/%s/action$" % (UUID_RE, UUID_RE))
        self.position = 2
        self.black_list += [
            self.attach_volume_action,
            self.extend_volume_action,
        ]
        self.resource_regexs = [
            self.resource_regex,
            self.volume_action_regex,
        ]
        self.resize_resource_actions = [
            self.extend_volume_action,
        ]
        self.product_items = extension.ExtensionManager(
            namespace='gringotts.volume.product_items',
            invoke_on_load=True,
            invoke_args=(self.gclient,))

    def attach_volume_action(self, method, path_info, body):
        if method == "POST" and \
                self.volume_action_regex.search(path_info) and \
                body.has_key('os-attach'):
            return True
        return False

    def extend_volume_action(self, method, path_info, body):
        if method == "POST" and \
                self.volume_action_regex.search(path_info) and \
                body.has_key('os-extend'):
            return True
        return False

    def parse_app_result(self, body, result, user_id, project_id):
        resources = []
        try:
            result = jsonutils.loads(result[0])
            if 'volume' in result:
                volume = result['volume']
                if 'display_name' in volume:
                    resource_name = volume['display_name'] # v1
                elif 'name' in volume:
                    resource_name = volume['name'] # v2
                else:
                    resource_name = None
                resources.append(base.Resource(
                    resource_id=volume['id'],
                    resource_name=resource_name,
                    type=const.RESOURCE_VOLUME,
                    status=const.STATE_RUNNING,
                    user_id=user_id,
                    project_id=project_id))
            elif 'snapshot' in result:
                snapshot = result['snapshot']
                resources.append(base.Resource(
                    resource_id=snapshot['id'],
                    resource_name=snapshot['name'],
                    type=const.RESOURCE_SNAPSHOT,
                    status=const.STATE_RUNNING,
                    user_id=user_id,
                    project_id=project_id))
        except Exception:
            return []
        return resources

    def resize_resource_order(self, env, body, start_response,
                              order_id, resource_id,
                              resource_type):
        quantity = body['os-extend'].get('new_size')

        try:
            self.gclient.resize_resource_order(order_id,
                                               quantity=quantity,
                                               resource_type=resource_type)
        except Exception:
            msg = "Unbale to resize the order: %s" % order_id
            LOG.exception(msg)
            return False, self._reject_request_500(env, start_response)

        return True, None


def filter_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)

    def bill_filter(app):
        return CinderBillingProtocol(app, conf)
    return bill_filter
