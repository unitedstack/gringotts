#!/usr/bin/python
# -*- coding: utf-8 -*-

import csv
import json
import requests
from gringotts.client import client
from gringotts.services import keystone

from xlwt import Workbook

import sys
reload(sys)
sys.setdefaultencoding('utf-8')


OS_AUHT_URL = 'http://localhost:35357/v3'

client = client.Client(username='admin',
                       password='rachel',
                       project_name='admin',
                       auth_url=OS_AUHT_URL)

__, accounts = client.get('/accounts')


def get_uos_user(user_id):

    internal_api = lambda api: OS_AUHT_URL + '/US-INTERNAL'+ '/' + api

    query = {'query': {'id': user_id}}
    r = requests.post(internal_api('get_user'),
                      data=json.dumps(query),
                      headers={'Content-Type': 'application/json'})
    if r.status_code == 404:
        return
    return r.json()['user']


book = Workbook(encoding='utf-8')
sheet1 = book.add_sheet('Sheet1')

COLUMNS = [u"邮箱", u"电话", u"姓名", u"公司", u"注册时间",
           u"账户余额(元)", u"bonus充值(元)", u"money充值(元)", u"消费总额(元)", u"预估每天消费(元)",
           u"user_id"]

for i in range(len(COLUMNS)):
    sheet1.write(0, i, COLUMNS[i])


j = 1
for account in accounts['accounts']:
    contact = get_uos_user(account['user_id'])
    if not contact:
        continue
    print account['user_id']
    balance = round(float(account['balance']), 4)
    consumption = round(float(account['consumption']), 4)
    __, consumption_per_day = client.get('/accounts/%s/estimate_per_day' % \
            account['user_id'])
    __, charges = client.get('/accounts/%s/charges' % account['user_id'])
    bonus = 0
    money = 0
    for charge in charges['charges']:
        if charge['type'] == 'bonus':
            bonus += float(charge['value'])
        elif charge['type'] == 'money':
            money += float(charge['value'])

    username = contact.get('real_name') or contact['email']
    mobile_number = contact.get('mobile_number') or 'unknown'
    email = contact.get('email')
    company = contact.get('company') or 'unknown'
    created_at = contact.get('created_at') or account['created_at'] or 'unknown'

    sheet1.write(j, 0, email)
    sheet1.write(j, 1, mobile_number)
    sheet1.write(j, 2, username)
    sheet1.write(j, 3, company)
    sheet1.write(j, 4, created_at)
    sheet1.write(j, 5, balance)
    sheet1.write(j, 6, bonus)
    sheet1.write(j, 7, money)
    sheet1.write(j, 8, consumption)
    sheet1.write(j, 9, consumption_per_day['price_per_day'])
    sheet1.write(j, 10, account['user_id'])
    j += 1

sheet1.col(0).width = 10000
sheet1.col(1).width = 5000
sheet1.col(2).width = 5000
sheet1.col(3).width = 10000
sheet1.col(4).width = 6000
sheet1.col(5).width = 4000
sheet1.col(6).width = 4000
sheet1.col(7).width = 4000
sheet1.col(8).width = 4000
sheet1.col(9).width = 4000
sheet1.col(10).width = 10000

book.save('accounts.xls')
