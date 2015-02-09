import re
from gringotts.middleware import base


UUID_RE = r"([0-9a-f]{32}|[0-9a-z]{8}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{12})"
RESOURCE_RE = r"(shares)"


def create_resource_action(method, path_info, body):
    if method == "POST" and re.match(r"^/%s/%s([.][^.]+)?$" % (UUID_RE, RESOURCE_RE), path_info):
        return True
    return False


class ManilaBillingProtocol(base.BillingProtocol):
    black_list  = [
        create_resource_action,
    ]


def filter_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)

    def bill_filter(app):
        return ManilaBillingProtocol(app, conf)
    return bill_filter
