# -*- coding: utf-8 -*-

import json
import requests

TEMPLATE_API_URL = "http://sendcloud.sohu.com/webapi/mail.send_template.xml"

PARAMS = {
    'api_user': 'postmaster@unitedstack-trigger.sendcloud.org',
    'api_key': '7CVvlTcXvVDgMo8U',
    'from': 'notice@mail.unitedstack.com',
    'fromname': 'UnitedStack',
    'replyto': 'support@unitedstack.com'
}


f = open('/tmp/users.txt')
_users = f.readlines()


users = []

for user in _users:
    users.append(user.strip('\n'))


def send_message(to):

    if not isinstance(to, list):
        to = [to]

    PARAMS['subject'] = u"[UnitedStack] 安全公告：Shellshock #2 #3 漏洞公告 (CVE-2014-7186 CVE-2014-7187 CVE-2014-6277 CVE-2014-6278)"
    PARAMS['template_invoke_name'] = 'breakdown'
    PARAMS['substitution_vars'] = json.dumps({'to': to,
                                              'sub': {}})
    r = requests.post(TEMPLATE_API_URL, data=PARAMS, verify=False)

for user in users:
    print 'sending: %s' % user
    send_message(user)
