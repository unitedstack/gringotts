from gringotts.client import client

client = client.Client(username='admin',
                       password='rachel',
                       project_name='admin',
                       auth_url='http://localhost:35357/v3')

__, precharges = client.get('/precharge')


f1 = open('ticket.log')
tickets = f1.readlines()

f2 = open('ticket2.log', 'w')

emails = []
codes = []

for ticket in tickets:
    emails.append(ticket.strip('\n').split(' ')[1])

number = len(emails)

for precharge in precharges:
    if precharge['used'] or precharge['dispatched']:
        continue
    code = precharge['code']
    codes.append("%s-%s-%s-%s" % (code[0:4], code[4:8], code[8:12], code[12:16]))

    if len(codes) == number:
        break

assert(len(codes) == number)

email_code = zip(emails, codes)

for email, code in email_code:
    _body = dict(remarks=email)
    _code = code.replace('-', '')
    client.put('/precharge/%s/dispatched' % _code, body=_body)
    f2.write('%s %s\n' % (code, email))

f1.close()
f2.close()
