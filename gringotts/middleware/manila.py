import re
from gringotts.middleware import base


UUID_RE = r"([0-9a-f]{32}|[0-9a-z]{8}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{12})"
RESOURCE_RE = r"(shares)"


class ManilaBillingProtocol(base.BillingProtocol):

    def __init__(self, app, conf):
        super(ManilaBillingProtocol, self).__init__(app, conf)
        self.resource_regex = re.compile(
            r"^/%s/%s/%s([.][^.]+)?$" % (UUID_RE, RESOURCE_RE, UUID_RE), re.UNICODE)
        self.create_resource_regex = re.compile(
            r"^/%s/%s([.][^.]+)?$" % (UUID_RE, RESOURCE_RE), re.UNICODE)
        self.position = 2
        self.resource_regexs = [
            self.resource_regex,
        ]


def filter_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)

    def bill_filter(app):
        return ManilaBillingProtocol(app, conf)
    return bill_filter
