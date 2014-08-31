# -*- coding: utf-8 -*-
import json
import requests
import datetime
from tempfile import TemporaryFile
from xlwt import Workbook

from gringotts.client import client
from gringotts.openstack.common import timeutils


OS_AUHT_URL = 'http://localhost:35357/v3'

client = client.Client(username='admin',
                       password='password',
                       project_name='admin',
                       auth_url=OS_AUHT_URL)


def get_uos_users(user_ids):

    internal_api = lambda api: OS_AUHT_URL + '/US-INTERNAL'+ '/' + api

    query = {'query': {'user_ids': user_ids}}
    r = requests.post(internal_api('get_users'),
                      data=json.dumps(query),
                      headers={'Content-Type': 'application/json'})
    return r.json()['users']


def get_new_accounts(y):
    __, accounts = client.get('/accounts')

    user_ids = []
    start_time = datetime.datetime(y.year, y.month, y.day, 1, 0, 0).replace(tzinfo=None)
    end_time = start_time + datetime.timedelta(days=1)

    for account in accounts['accounts']:
        created_at = timeutils.parse_isotime(account['created_at']).replace(tzinfo=None)
        if created_at > start_time and created_at < end_time:
            user_ids.append(account['user_id'])

    return user_ids


# import new accounts
book = Workbook(encoding='utf-8')
sheet1 = book.add_sheet('Sheet1')

COLUMNS = [u"姓名(必填)", u"负责员工", u"性别", u"出生年份", u"出生月份", u"出生日期", u"公司", u"部门", u"职务", u"地址", u"网址", u"兴趣爱好",
           u"备注", u"电话", u"手机", u"电子邮件", u"传真", u"新浪微博", u"腾讯微博", u"微信", u"QQ", u"MSN"]
DUTY_MAN = [u"安继", u"赵京", u"陈方日"]
yesterday = datetime.date.today() - datetime.timedelta(days=1)


for i in range(len(COLUMNS)):
    sheet1.write(0, i, COLUMNS[i])


users = get_uos_users(get_new_accounts(yesterday))
duty_man = DUTY_MAN[yesterday.day % len(DUTY_MAN)]


for j in range(len(users)):
    real_name = users[j].get('real_name') or users[j]['email'].split('@')[0]
    mobile_number = users[j].get('mobile_number') or "unknown"
    email = users[j]['email']
    company = users[j].get('company') or "unknown"

    sheet1.write(j+1, 0, real_name)
    sheet1.write(j+1, 1, duty_man)
    sheet1.write(j+1, 6, company)
    sheet1.write(j+1, 14, mobile_number)
    sheet1.write(j+1, 15, email)

sheet1.col(0).width = 5000
sheet1.col(1).width = 5000
sheet1.col(6).width = 10000
sheet1.col(14).width = 10000
sheet1.col(15).width = 10000

book.save('/tmp/accounts-%s.xls' % yesterday)
book.save(TemporaryFile())

# send email
url="https://sendcloud.sohu.com/webapi/mail.send.xml"
files = {"new_accounts": ("accounts-%s.xls" % yesterday, open("/tmp/accounts-%s.xls" % yesterday))}
params = {"api_user": "postmaster@unitedstack-trigger.sendcloud.org",
          "api_key": "password",
          "from": "notice@mail.unitedstack.com",
          "fromname": "UnitedStack",
          "to": "578579544@qq.com;guangyu@unitedstack.com",
          "subject": '[UnitedStack][%s]新增用户' % yesterday,
          "html": "[%s]共新增用户[%s]个，具体见附件。" % (yesterday, len(users))}

r = requests.post(url, files=files, data=params)
