import re
from gringotts.middleware import base


UUID_RE = r"([0-9a-f]{32}|[0-9a-z]{8}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{12})"
API_VERSION = r"(v1|v2)"


def start_alarm_action(method, path_info, body):
    if method == "PUT" and re.match(r"^/v2/alarms/%s/switch$" % UUID_RE, path_info) and body == 'on':
        return True
    return False


def create_resource_action(method, path_info, body):
    if method == "POST" and re.match(r"^/%s/alarms([.][^.]+)?$" % API_VERSION , path_info):
        return True
    return False


class CeilometerBillingProtocol(base.BillingProtocol):
    black_list  = [
        create_resource_action,
        start_alarm_action,
    ]


def filter_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)

    def bill_filter(app):
        return CeilometerBillingProtocol(app, conf)
    return bill_filter
