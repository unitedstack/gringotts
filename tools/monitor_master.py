# coding: utf-8
import sys
import time
import datetime
import hashlib
import urllib
import json
import requests
from gringotts.client import client

ISO8601_TIME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
SMS_API_URL = "http://q.hl95.com:8061"


CLOUDS = {"uos": {"os_auth_url": "http://i.l7.0.uc.ustack.in:35357/v3",
                  "regions": ["bj1", "gd1"],
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
          "lxy": {"os_auth_url": "http://l7.0.lxy.ustack.in:35357/v3",
                 "regions": ["RegionOne"],
                 "admin_user": "admin",
                 "admin_password": "password",
                 "admin_tenant_name": "admin"},
          "ghxw": {"os_auth_url": "http://l7.0.ghxw.ustack.in:35357/v3",
                 "regions": ["RegionOne"],
                 "admin_user": "admin",
                 "admin_password": "password",
                 "admin_tenant_name": "admin"},
          "wywl": {"os_auth_url": "http://i.l7.7.wywl.ustack.in:35357/v3",
                 "regions": ["xm1", "tw1"],
                 "admin_user": "admin",
                 "admin_password": "password",
                 "admin_tenant_name": "admin"},
}


def parse_strtime(timestr, fmt=ISO8601_TIME_FORMAT):
    """Turn a formatted time back into a datetime."""
    return datetime.datetime.strptime(timestr, fmt)


def get_one_active_order(client, region_id):
    _, resp = client.get('/orders/active?region_id=%s&limit=1&offset=0' % region_id)
    return resp[0] if resp else None


def alert_to(content, recipients):

    params = {'username': 'ysd',
              'password': hashlib.new("md5", 'password').hexdigest(),
              'epid': '109830',
              'message': content.encode('gb2312')}

    utc_now = datetime.datetime.utcnow()
    for recip in recipients:
        params.update(phone=recip)
        resp = requests.get(SMS_API_URL + '?' + urllib.urlencode(params))
        print "%s %s" % (utc_now, resp.content)


if __name__ == '__main__':
    while True:
        for cloud_name, cloud in CLOUDS.items():
            try:
                gclient = client.Client(username=cloud['admin_user'],
                                        password=cloud['admin_password'],
                                        project_name=cloud['admin_tenant_name'],
                                        auth_url=cloud['os_auth_url'])
                for region_name in cloud['regions']:
                    order = get_one_active_order(gclient, region_name)
                    if not order:
                        print "there is no active order in [%s][%s]." % (cloud_name, region_name)
                        continue
                    cron_time = parse_strtime(order['cron_time'])
                    utc_now = datetime.datetime.utcnow()
                    if utc_now > cron_time:
                        alert_to(u"【UnitedStack有云】[%s][%s] gring-master maybe hanged, check it" % (cloud_name, region_name),
                                 ["18500239557"])
            except Exception as e:
                print "some error happen when checking in %s: %s" % (cloud_name, e)
        time.sleep(3600)
