# -*- coding: utf-8 -*-
import json
import requests
import datetime

CLOUDS = {"uos": {"os_auth_url": "http://i.l7.0.uc.ustack.in:35357/v3",
                  "regions": ["RegionOne", "zhsh"],
                  "admin_user": "admin",
                  "admin_password": "password",
                  "admin_tenant_name": "admin"},
          "mm": {"os_auth_url": "http://l7.0.mm.ustack.in:35357/v3",
                 "regions": ["RegionOne"],
                 "admin_user": "admin",
                 "admin_password": "password",
                 "admin_tenant_name": "admin"},
          "zhj": {"os_auth_url": "http://l7.0.zhj.ustack.in:35357/v3",
                 "regions": ["RegionOne"],
                 "admin_user": "admin",
                 "admin_password": "password",
                 "admin_tenant_name": "admin"},
          "sh": {"os_auth_url": "http://l7.0.sh.ustack.in:35357/v3",
                 "regions": ["RegionOne"],
                 "admin_user": "admin",
                 "admin_password": "password",
                 "admin_tenant_name": "admin"},
}

RESOURCE_TYPE = ["instance", "volume", "floatingip"]


def force_v3_api(url):
    if url is none:
        return url
    if url.endswith('/v2.0'):
        return url.replace('/v2.0', '/v3')
    return url


ks_client = None


def get_ks_client(admin_user, admin_password, admin_tenant_name, os_auth_url):
    global ks_client
    if ks_client is None:
        ks_client = client.Client(user_domain_name="Default"
                                  username=admin_user,
                                  password=admin_password,
                                  project_domain_name="Default",
                                  project_name=admin_tenant_name,
                                  auth_url=os_auth_url)
        ks_client.management_url = force_v3_api(ks_client.management_url)
    return ks_client


resource_count = []
for region in REGIONS:
    line = (region,)
    line = line + tuple((get_resource_count(region, type) for type in RESOURCE_TYPE))
    resource_count.append(line)

yesterday = datetime.date.today() - datetime.timedelta(days=1)

# send email
content = u"<p>[%s]资源报表:</p>" % yesterday
content += u"<table border=\"1\" style=\"border-collapse:collapse;\"><thead><tr><th>区域</th><th>主机</th><th>云硬盘</th><th>公网IP</th></tr></thead>"
for line in resource_count:
    content += u"<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (line[0], line[1], line[2], line[3])
content += u"</table><br/>"

url="https://sendcloud.sohu.com/webapi/mail.send.xml"

params = {"api_user": "postmaster@unitedstack-trigger.sendcloud.org",
          "api_key": "7CVvlTcXvVDgMo8U",
          "from": "notice@mail.unitedstack.com",
          "fromname": "UnitedStack",
          #"to": "support@unitedstack.com",
          "to": "guangyu@unitedstack.com",
          "subject": '[UnitedStack][%s]资源报表' % yesterday,
          "template_invoke_name": "register",
          "html": content.encode('utf-8')}

r = requests.post(url, data=params)
