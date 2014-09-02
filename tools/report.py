#!/usr/bin/python
# -*- coding: utf-8 -*-

import csv
from gringotts.client import client
from gringotts.services import keystone


client = client.Client(username='admin',
                       password='rachel',
                       project_name='admin',
                       auth_url='http://localhost:35357/v3')

__, accounts = client.get('/accounts')


csvfile = open('billing_report.csv', 'wb')
c = csv.writer(csvfile, dialect='excel')
c.writerow(['姓名', '电话', '邮箱', '公司', '账户余额(元)', '消费总额(元)', '预估每天消费(元)'])

for account in accounts:

    contact = keystone.get_uos_user(account['user_id'])
    balance = float(account['balance'])
    consumption = float(account['consumption'])
    __, consumption_per_day = client.get('/accounts/%s/estimate_per_day' % \
            account['project_id'])

    username = contact.get('real_name') or contact['email']
    mobile_number = contact.get('mobile_number') or 'unknown'
    email = contact.get('email')
    company = contact.get('company') or 'unknown'

    c.writerow([username, mobile_number, email, company, balance, consumption, consumption_per_day])
