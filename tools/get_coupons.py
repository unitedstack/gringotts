from gringotts.client import client

client = client.Client(username='admin',
                       password='rachel',
                       project_name='admin',
                       auth_url='http://localhost:35357/v3')

__, precharges = client.get('/precharge')


codes = []

for precharge in precharges:
    if precharge['used'] or precharge['dispatched']:
        continue
    code = precharge['code']
    code = "%s-%s-%s-%s" % (code[0:4], code[4:8], code[8:12], code[12:16])
    print code
