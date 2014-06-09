import json
import requests

from oslo.config import cfg


OPTS = [
    cfg.StrOpt('alert_url',
               default='http://localhost:8080',
               help="The endpoint of the alert api"),
    cfg.StrOpt('alert_to',
               default='all',
               help="Alert to who"),
    cfg.IntOpt('alert_priority',
               default=1,
               help="Priority of alert")
]
cfg.CONF.register_opts(OPTS)


ALERT_CLIENT = None
alert_api = lambda url: "%s/v1/%s" % (cfg.CONF.alert_url, url)
RECIPIENTS = ['product', 'storage', 'network', 'devops']


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
    subject = "[Alert] There are some bad resources in ustack cloud"
    tags = None
    priority = cfg.CONF.alert_priority

    #Format alert content: resource_id, resource_name, resource_type, tenant_id, status
    body = "<html><body><table border=1px>"\
           "<tr><th>Resource ID</th><th>Resource Name</th>"\
           "<th>Resource Type</th><th>Tenant ID</th><th>Status</th>"\
           "</tr>%s</table></body></html>"
    trs = ""
    for resource in resources:
        tr = "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % \
             (resource.id, resource.name, resource.resource_type,
              resource.project_id,resource.original_status)
        trs += tr
    body = body % trs

    content = {
        'alert_title': subject,
        'alert_tag': tags,
        'alert_priority': priority,
        'alert_content': body,
        'alert_group': to
    }

    if to == 'all':
        for recip in RECIPIENTS:
            content.update(alert_group=recip)
            alert_client().post(alert_api('alerts'),
                                data=json.dumps(content))
    else:
        alert_client().post(alert_api('alerts'),
                            data=json.dumps(content))
