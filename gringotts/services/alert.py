import os
import json
import requests

from oslo.config import cfg
from gringotts.openstack.common import log


LOG = log.getLogger(__name__)


OPTS = [
    cfg.StrOpt('alert_url',
               default='http://alerting.ustack.com:8080',
               help="The endpoint of the alert api"),
    cfg.StrOpt('alert_to',
               default='all',
               help="Alert to who"),
    cfg.IntOpt('alert_priority',
               default=2,
               help="Priority of alert"),
    cfg.BoolOpt('enable_alert',
                default=False,
                help="Enable the alert or not")
]
cfg.CONF.register_opts(OPTS)


ALERT_CLIENT = None
alert_api = lambda url: "%s/v1/%s" % (cfg.CONF.alert_url, url)
RECIPIENTS = ['devops', 'product', 'storage', 'network']


def alert_client():
    global ALERT_CLIENT
    if ALERT_CLIENT is None:
        s = requests.Session()
        s.headers.update({'Content-Type': 'application/json'})
        ALERT_CLIENT = s
        return s
    return ALERT_CLIENT


def alert_bad_resources(resources):
    to = cfg.CONF.alert_to
    subject = "[Alert in Region: %s] There are some bad resources in ustack cloud" % cfg.CONF.region_name
    tags = 'resource;report'
    priority = cfg.CONF.alert_priority

    alert_path = "%s/alert.html" % os.path.split(os.path.realpath(__file__))[0]
    with open(alert_path) as f:
        body = f.read().replace("\n", "")

    trs = ""
    for resource in resources:
        LOG.warn('The resource(%s) is in bad status for a certain time.' %
                 resource.as_dict())
        tr = "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % \
             (resource.id, resource.name, resource.resource_type,
              resource.original_status,resource.project_id, resource.project_name)
        trs += tr
    body = body % trs

    content = {
        'alert_title': subject,
        'alert_tag': tags,
        'alert_priority': priority,
        'alert_content': body,
        'alert_group': to
    }

    if not cfg.CONF.enable_alert:
        return

    if to == 'all':
        for recip in RECIPIENTS:
            content.update(alert_group=recip)
            alert_client().post(alert_api('alerts'),
                                data=json.dumps(content))
    else:
        alert_client().post(alert_api('alerts'),
                            data=json.dumps(content))
    LOG.warn('Send alert emails successfully')
