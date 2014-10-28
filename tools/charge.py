import sys
import json
import requests
from gringotts.client import client

OS_AUHT_URL = 'http://localhost:35357/v3'

client = client.Client(username='admin',
                       password='rachel',
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


def charge_account(project_id, value, type, come_from):
    body = dict(value=value,
                type=type,
                come_from=come_from)
    client.put('/accounts/%s' % project_id, body=body)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print 'usage: python charge.py <email> <value> [type] [come_from]'
        sys.exit()

    email = sys.argv[1]

    try:
        float(sys.argv[2])
    except ValueError:
        sys.exit("Invalid value, should be an number")

    if float(sys.argv[2]) < 0:
        sys.exit("Invalid value, should be greater than 0")

    value = sys.argv[2]

    try:
        type = sys.argv[3]
    except IndexError:
        type = 'bonus'

    try:
        come_from = sys.argv[4]
    except IndexError:
        come_from = 'system'

    if type not in ('bonus', 'money'):
        sys.exit('Invalid type')

    if come_from not in ('system', 'alipay', 'bank'):
        sys.exit('Invalid come_from')


    project_id = get_uos_user(email)['default_project_id']
    charge_account(project_id, value, type, come_from)
    #user_id = get_uos_user(email)['id']
    #charge_account(user_id, value, type, come_from)
