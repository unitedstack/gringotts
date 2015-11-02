import re
from stevedore import extension

from gringotts import constants as const
from gringotts.middleware import base
from gringotts.openstack.common import jsonutils
from gringotts.price import pricing


UUID_RE = r'([0-9a-f]{32}' \
    r'|[0-9a-z]{8}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{12})'
RESOURCE_RE = r'(routers|floatingips|floatingipsets|lbaas/listeners)'


class RateLimitItem(base.ProductItem):
    service = const.SERVICE_NETWORK

    def get_product_name(self, body):
        result = const.PRODUCT_FLOATINGIP
        providers = None
        if 'floatingip' in body:
            providers = body['floatingip'].get('uos:service_provider')
        elif 'floatingipset' in body:
            providers = body['floatingipset'].get('uos:service_provider')
        if providers:
            providers = sorted(list(providers))
            result = result + ('-'.join(providers))
        return result

    def get_resource_volume(self, body):
        if 'floatingip' in body:
            rate_limit = body['floatingip'].get('rate_limit')
        elif 'floatingipset' in body:
            rate_limit = body['floatingipset'].get('rate_limit')
        else:
            rate_limit = 1024
        return pricing.rate_limit_to_unit(rate_limit)


class NeutronBillingProtocol(base.BillingProtocol):

    def __init__(self, app, conf):
        super(NeutronBillingProtocol, self).__init__(app, conf)
        self.resource_regex = re.compile(
            r'^/%s/%s([.][^.]+)?$' % (RESOURCE_RE, UUID_RE), re.UNICODE)
        self.create_resource_regex = re.compile(
            r'^/%s([.][^.]+)?$' % RESOURCE_RE, re.UNICODE)

        self.change_fip_ratelimit_regex = re.compile(
            r'^/(uos_resources)/%s/'
            r'update_floatingip_ratelimit([.][^.]+)?$' % (UUID_RE))
        self.change_fipset_ratelimit_regex = re.compile(
            r'^/(uos_resources)/%s/'
            r'update_floatingipset_ratelimit([.][^.]+)?$' % (UUID_RE))
        self.update_listener_regex = re.compile(
            r'^/(lbaas/listeners)/%s([.][^.]+)?$' % (UUID_RE))

        self.position = 1
        self.black_list += [
            self.change_fip_ratelimit_action,
            self.change_fipset_ratelimit_action,
            self.update_listener,
            self.switch_listener,
        ]
        self.resource_regexs = [
            self.resource_regex,
            self.change_fip_ratelimit_regex,
            self.change_fipset_ratelimit_regex,
            self.update_listener_regex,
        ]
        self.resize_resource_actions = [
            self.change_fip_ratelimit_action,
            self.change_fipset_ratelimit_action,
            self.update_listener,
        ]
        self.product_items = extension.ExtensionManager(
            namespace='gringotts.floatingip.product_items',
            invoke_on_load=True,
            invoke_args=(self.gclient,))

    def change_fip_ratelimit_action(self, method, path_info, body):
        if method == 'PUT' \
            and self.change_fip_ratelimit_regex.search(path_info):
            return True
        return False

    def change_fipset_ratelimit_action(self, method, path_info, body):
        if method == 'PUT' \
            and self.change_fipset_ratelimit_regex.search(path_info):
            return True
        return False

    def switch_listener(self, method, path_info, body):
        if method == 'PUT' \
            and  self.update_listener_regex.search(path_info) \
            and 'admin_state_up' in body['listener']:
            return True
        return False

    def update_listener(self, method, path_info, body):
        if method == 'PUT' \
            and  self.update_listener_regex.search(path_info) \
            and 'connection_limit' in body['listener']:
            return True
        return False

    def parse_app_result(self, body, result, user_id, project_id):
        resources = []
        try:
            result = jsonutils.loads(result[0])
            if 'floatingip' in result:
                fip = result['floatingip']
                resources.append(base.Resource(
                    resource_id=fip['id'],
                    resource_name=fip.get('uos:name'),
                    type=const.RESOURCE_FLOATINGIP,
                    status=const.STATE_RUNNING,
                    user_id=user_id,
                    project_id=project_id
                ))
            elif 'floatingipset' in result:
                fipset = result['floatingipset']
                resources.append(base.Resource(
                    resource_id=fipset['id'],
                    resource_name=fipset.get('uos:name'),
                    type=const.RESOURCE_FLOATINGIPSET,
                    status=const.STATE_RUNNING,
                    user_id=user_id,
                    project_id=project_id
                ))
        except Exception:
            return []
        return resources


def filter_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)

    def bill_filter(app):
        return NeutronBillingProtocol(app, conf)
    return bill_filter
