import re

from gringotts.middleware import base


UUID_RE = r'([0-9a-f]{32}' \
    r'|[0-9a-z]{8}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{12})'
RESOURCE_RE = r'(routers|floatingips|floatingipsets|lbaas/listeners)'


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
        ]
        self.resource_regexs = [
            self.resource_regex,
            self.change_fip_ratelimit_regex,
            self.change_fipset_ratelimit_regex,
            self.update_listener_regex,
        ]

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

    def update_listener(self, method, path_info, body):
        if method == 'PUT' \
            and  self.update_listener_regex.search(path_info) \
            and (('connection_limit' in body['listener'])
                 or ('admin_state_up' in body['listener'])):
            return True
        return False


def filter_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)

    def bill_filter(app):
        return NeutronBillingProtocol(app, conf)
    return bill_filter
