import sys
import json
import requests
from gringotts.client import client

OS_AUHT_URL = 'http://localhost:35357/v3'

client = client.Client(username='admin',
                       password='rachel',
                       project_name='admin',
                       auth_url=OS_AUHT_URL)


def get_resources(project_id, region_name=None):
    params = dict(project_id=project_id,
                  region_name=region_name)
    _, resources = client.get('/resources', params=params)
    for r in resources:
        print "%s %s %s %s" % (r['region_name'], r['resource_id'],
                               r['resource_type'], r['resource_name'])


def delete_resources(project_id, region_name=None):
    _body = dict(project_id=project_id,
                 region_name=region_name)
    client.delete("/resources", body=_body)


if __name__ == '__main__':

    if len(sys.argv) < 3:
        print 'usage: python resource.py <get|delete> <project_id> [region_name]'
        sys.exit()

    action = sys.argv[1]

    if action not in ("get", "delete"):
        sys.exit("Invalid action, should be get or delete")

    project_id = sys.argv[2]

    try:
        region_name = sys.argv[3]
    except IndexError:
        region_name = None

    if action == 'get':
        get_resources(project_id, region_name=region_name)
    elif action == 'delete':
        delete_resources(project_id, region_name=region_name)
