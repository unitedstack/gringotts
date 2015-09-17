import re
from gringotts.middleware import base


UUID_RE = r"([0-9a-f]{32}|[0-9a-z]{8}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{12})"
RESOURCE_RE = r"(volumes|snapshots)"



class CinderBillingProtocol(base.BillingProtocol):

    def __init__(self, app, conf):
        super(CinderBillingProtocol, self).__init__(app, conf)
        self.resource_rex = re.compile(
            r"^/%s/%s/%s([.][^.]+)?$" % (UUID_RE, RESOURCE_RE, UUID_RE), re.UNICODE)
        self.create_resource_regex = re.compile(
            r"^/%s/%s([.][^.]+)?$" % (UUID_RE, RESOURCE_RE), re.UNICODE)
        self.volume_action_regex = re.compile(
            r"^/%s/(volumes)/%s/action$" % (UUID_RE, UUID_RE))
        self.position = 2
        self.black_list += [
            attach_volume_action,
        ]
        self.resource_regexs = [
            self.resource_regex,
            self.volume_action_regex,
        ]

    def attach_volume_action(self, method, path_info, body):
        if method == "POST" and \
                self.volume_action_regex.search(path_info) and \
                (body.has_key('os-attach') or \
                 body.has_key('os-extend')):
            return True
        return False


def filter_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)

    def bill_filter(app):
        return CinderBillingProtocol(app, conf)
    return bill_filter
