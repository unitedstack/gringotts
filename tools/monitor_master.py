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
OS_AUHT_URL = 'http://localhost:35357/v3'
SMS_API_URL = "http://q.hl95.com:8061"


client = client.Client(username='demo',
                       password='rachel',
                       project_name='demo',
                       auth_url=OS_AUHT_URL)


def parse_strtime(timestr, fmt=ISO8601_TIME_FORMAT):
    """Turn a formatted time back into a datetime."""
    return datetime.datetime.strptime(timestr, fmt)


def get_order(order_id):
    return client.get('/orders/%s/order' % order_id)


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
        try:
            _, order = get_order("2437aa8b-e8b1-496e-918e-02f1d05f2b10")
            cron_time = parse_strtime(order['cron_time'])
            utc_now = datetime.datetime.utcnow()
            if utc_now > cron_time:
                alert_to(u"【UnitedStack有云】gring-master maybe hanged, check it",
                         ["18500239557"])
        except Exception as e:
            print "some error happen: %s" % e
        time.sleep(3600)
