from gringotts.client import client

client = client.Client(username='admin',
                       password='rachel',
                       project_name='admin',
                       auth_url='http://localhost:35357/v3')

__, accounts = client.get('/accounts')

for account in accounts:

    if account['project_id'] == '6366f4fe38f54c3a96c62e90c088490a':
        continue

    balance = float(account['balance'])

    # fill balance to 0
    if balance < 0:
        body = dict(value=-balance,
                    type='bonus',
                    come_from='system')
        client.put('/accounts/%s' % account['project_id'], body=body)

    # charge 20RMB
    body = dict(value=20,
                type='bonus',
                come_from='system')
    client.put('/accounts/%s' % account['project_id'], body=body)
