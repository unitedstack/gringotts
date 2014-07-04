from gringotts.client import client

client = client.Client(username='admin',
                       password='rachel',
                       project_name='admin',
                       auth_url='http://localhost:35357/v3')

__, accounts = client.get('/accounts')

for account in accounts:

    charges = client.get('/accounts/%s/charges' % account['project_id'])[1]['charges']

    value = 0

    for charge in charges:
        if charge['type'] == 'money':
            value += float(charge['value'])

    if value > 0:
        # charge 20RMB
        body = dict(value=str(value),
                    type='bonus',
                    come_from='system')
        client.put('/accounts/%s' % account['project_id'], body=body)
