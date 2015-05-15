import sys
import json
import requests
from gringotts.client import client

OS_AUHT_URL = 'http://localhost:35357/v3'

client = client.Client(username='admin',
                       password='rachel',
                       project_name='admin',
                       auth_url=OS_AUHT_URL)

def charge_account(project_id, value, type, come_from):
    body = dict(value=value,
                type=type,
                come_from=come_from,
                remarks="reset balance to 0")
    client.put('/accounts/%s' % project_id, body=body)


def get_accounts():
    __, accounts = client.get('/accounts')
    return accounts['accounts']

if __name__ == '__main__':
    accounts = get_accounts()
    for account in accounts:
        user_id = account['user_id']
        balance = account['balance']
        if balance == '0.0000':
            continue
        value = balance[1:-1] if balance.startswith('-') else "-%s" % balance
        charge_account(user_id, value, 'bonus', 'system')
