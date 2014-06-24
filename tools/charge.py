from gringotts.client import client

client = client.Client(username='admin',
                       password='rachel',
                       project_name='admin',
                       auth_url='http://localhost:35357/v3')

__, accounts = client.get('/accounts')

for account in accounts:
    value = float(account['consumption'])
    if value <= 0:
        continue
    balance = float(account['balance'])
    if balance > 0:
        continue
    body = dict(value=account['consumption'],
                type='bonus',
                come_from='system')
    client.put('/accounts/%s' % account['project_id'], body=body)
