import re
from gringotts.middleware import base


UUID_RE = r"([0-9a-f]{32}|[0-9a-z]{8}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{12})"
API_VERSION = r"(v1|v2)"

def create_image_action_api(method, path_info, body):
    if method == "POST" and re.match(r"^/%s/images([.][^.]+)?$" % API_VERSION, path_info):
        return True
    return False


def create_image_action_registry(method, path_info, body):
    if method == "POST" and re.match(r"^/images([.][^.]+)?$", path_info):
        return True
    return False


class GlanceBillingProtocol(base.BillingProtocol):
    black_list  = [
        create_image_action_api,
        create_image_action_registry,
    ]


def filter_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)

    def bill_filter(app):
        return GlanceBillingProtocol(app, conf)
    return bill_filter
