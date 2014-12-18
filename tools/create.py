import sys
import json
import requests
from gringotts.client import client

OS_AUHT_URL = 'http://localhost:35357/v3'

client = client.Client(username='admin',
                       password='admin',
                       project_name='admin',
                       auth_url=OS_AUHT_URL)


def get_uos_user(email):

    internal_api = lambda api: OS_AUHT_URL + '/US-INTERNAL'+ '/' + api

    query = {'query': {'email': email}}
    r = requests.post(internal_api('get_user'),
                      data=json.dumps(query),
                      headers={'Content-Type': 'application/json'})
    if r.status_code == 404:
        sys.exit('can not find the user')
    return r.json()['user']


def charge_account(user_id, value, type, come_from):
    body = dict(value=value,
                type=type,
                come_from=come_from)
    client.put('/accounts/%s' % user_id, body=body)


def create_account(user_id, project_id, domain_id):
    body = dict(user_id=user_id,
                project_id=project_id,
                domain_id=domain_id,
                consumption='0',
                balance='0',
                level=3,
                currency='CNY')
    client.post('/accounts', body=body)


def create_project(user_id, project_id, domain_id):
    body = dict(user_id=user_id,
                project_id=project_id,
                domain_id=domain_id,
                consumption='0')
    client.post('/projects', body=body)


def get_account(user_id):
    try:
        __, account = client.get('/accounts/%s' % user_id)
    except Exception:
        return None
    return account


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print 'usage: python create.py <email> [balance]'
        sys.exit()

    email = sys.argv[1]
    try:
        balance = sys.argv[2]
    except IndexError:
        balance = '10'

    user = get_uos_user(email)

    account = get_account(user['id'])
    if account:
        sys.exit("Account %s has existed in billing service" % email)

    create_account(user['id'], user['default_project_id'], user['domain_id'])
    create_project(user['id'], user['default_project_id'], user['domain_id'])
    charge_account(user['id'], balance, 'bonus', 'system')
