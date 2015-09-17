import re
from gringotts.middleware import base


UUID_RE = r"([0-9a-f]{32}|[0-9a-z]{8}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{12})"
API_VERSION = r"(v1|v2)"
RESOURCE_RE = r"(alarms)"


class CeilometerBillingProtocol(base.BillingProtocol):

    def __init__(self, app, conf):
        super(CeilometerBillingProtocol, self).__init__(app, conf)
        self.resource_regex = re.compile(
            r"^/v2/%s/%s([.][^.]+)?$" % (RESOURCE_RE, UUID_RE), re.UNICODE)
        self.create_resource_regex = re.compile(
            r"^/%s/%s([.][^.]+)?$" % (API_VERSION, RESOURCE_RE))
        self.start_alarm_regex = re.compile(
            r"^/v2/(alarms)/%s/switch$" % UUID_RE)
        self.position = 1
        self.black_list += [
            self.start_alarm_action,
        ]
        self.resource_regexs = [
            self.resource_regex,
            self.start_alarm_regex,
        ]

    def start_alarm_action(self, method, path_info, body):
        if (method == "PUT" and body == 'on' and
            self.start_alarm_regex.search(path_info)):
            return True
        return False


def filter_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)

    def bill_filter(app):
        return CeilometerBillingProtocol(app, conf)
    return bill_filter
