import re
from gringotts.middleware import base


UUID_RE = r"([0-9a-f]{32}|[0-9a-z]{8}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{12})"
RESOURCE_RE = r"(os-volumes|os-snapshots|os-floating-ips|os-floating-ips-bulk|images)"


def create_server_action(method, path_info, body):
    # NOTE(suo): should handle the suffix
    if method == "POST" and re.match(r"^/%s/servers([.][^.]+)?$" % UUID_RE, path_info):
        return True
    return False


def other_server_actions(method, path_info, body):
    if method == "POST" and re.match(r"^/%s/servers/%s/action$" % (UUID_RE, UUID_RE), path_info) and \
            (body.has_key('os-start') or \
             body.has_key('createImage') or \
             body.has_key('addFloatingIp') or \
             body.has_key('reboot') or \
             body.has_key('rebuild') or \
             body.has_key('unpause') or \
             body.has_key('resume') or \
             body.has_key('unshelve') or \
             body.has_key('unrescue') or \
             body.has_key('resize')):
        return True
    return False


def create_other_resource_action(method, path_info, body):
    if method == "POST" and re.match(r"^/%s/%s([.][^.]+)?$" % (UUID_RE, RESOURCE_RE), path_info):
        return True
    return False


def attach_volume_to_server_action(method, path_info, body):
    if method == "POST" and re.match(r"^/%s/servers/%s/os-volume_attachments([.][^.]+)?$" % (UUID_RE, UUID_RE), path_info):
        return True
    return False


class NovaBillingProtocol(base.BillingProtocol):
    black_list  = [
        create_server_action,
        other_server_actions,
        create_other_resource_action,
        attach_volume_to_server_action,
    ]


def filter_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)

    def bill_filter(app):
        return NovaBillingProtocol(app, conf)
    return bill_filter
