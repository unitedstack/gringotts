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

    files = {"breakdown2": (u"IDC_maintenance_notification_20140919.docx", open(u"/tmp/IDC割接通知20140919.docx", "rb")),
             "breakdown1": (u"unicom_breakdown_report_20140919.jpg", open(u"/tmp/联通故障报告20140919.jpg", "rb"))}

    PARAMS['subject'] = u"[UnitedStack] 北京1区 9月20日凌晨 网络割接 通知"
    PARAMS['template_invoke_name'] = 'breakdown'
    PARAMS['substitution_vars'] = json.dumps({'to': to,
                                              'sub': {}})
    r = requests.post(TEMPLATE_API_URL, files=files, data=PARAMS, verify=False)

for user in users:
    print 'sending: %s' % user
    send_message(user)
