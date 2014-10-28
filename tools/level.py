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


def change_account_level(project_id, level):
    body = dict(level=level)
    client.put('/accounts/%s/level' % project_id, body=body)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print 'usage: python level.py <email> <level>'
        sys.exit()

    email = sys.argv[1]

    try:
        level = int(sys.argv[2])
        if level < 0 or level > 9:
            sys.exit("Invalid level, should be greater than 0 and less than 9")
    except ValueError:
        sys.exit("Invalid level, should be an integer")

    project_id = get_uos_user(email)['default_project_id']
    change_account_level(project_id, level)
