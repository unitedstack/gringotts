import re
from gringotts.middleware import base


UUID_RE = r"([0-9a-f]{32}|[0-9a-z]{8}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{12})"
API_VERSION = r"(v1|v2)"
RESOURCE_RE = r"(images)"


class GlanceBillingProtocol(base.BillingProtocol):

    def __init__(self, app, conf):
        super(GlanceBillingProtocol, self).__init__(app, conf)
        self.resource_regex = re.compile(
            r"^/%s/%s/%s([.][^.]+)?$" % (API_VERSION, RESOURCE_RE, UUID_RE), re.UNICODE)
        self.create_resource_regex = re.compile(
            r"^/%s/%s([.][^.]+)?$" % (API_VERSION, RESOURCE_RE), re.UNICODE)
        self.position = 2
        self.resource_regexs = [
            self.resource_regex,
        ]


def filter_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)

    def bill_filter(app):
        return GlanceBillingProtocol(app, conf)
    return bill_filter
