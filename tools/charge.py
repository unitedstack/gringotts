from gringotts.client import client

client = client.Client(username='admin',
                       password='rachel',
                       project_name='admin',
                       auth_url='http://localhost:35357/v3')

__, accounts = client.get('/accounts')

for account in accounts:
    balance = float(account['balance'])
    if balance > 20:
        continue
    value = str(float(account['consumption']) + 10)
    body = dict(value=value,
                type='bonus',
                come_from='system')
    client.put('/accounts/%s' % account['project_id'], body=body)
