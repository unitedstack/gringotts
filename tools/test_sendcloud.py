# coding: utf-8

import json
import requests

TEMPLATE_API_URL = "http://sendcloud.sohu.com/webapi/mail.send_template.xml"
#TEMPLATE_API_URL = "http://sendcloud.sohu.com/webapi/mail.send.xml"
PARAMS = {
    #'api_user': "senhua",
    'api_user': "postmaster@unitedstack-trigger.sendcloud.org",
    'api_key': "password",
    'from': "notice@senhuayun.com",
    'fromname': u"森华云"
}

def send_message(to, subject, message, template_name=None, **kwargs):
    if not template_name:
        raise Exception("template name is required by sendcloud")

    if not isinstance(to, list):
        to = [to]

    PARAMS['subject'] = subject
    PARAMS['template_invoke_name'] = template_name
    PARAMS['substitution_vars'] = json.dumps({'to': to,
                                              'sub': {'%msg_body%': [message]}})

    r = requests.post(TEMPLATE_API_URL, data=PARAMS)
    print r.text

send_message("guangyu@unitedstack.com", u"测试邮件标题3", u"这是一封来自UnitedStack的测试邮件", "default")
send_message("yugsuo@gmail.com", u"测试邮件标题3", u"这是一封来自UnitedStack的测试邮件", "default")
send_message("578579544@qq.com", u"测试邮件标题3", u"这是一封来自UnitedStack的测试邮件", "default")
send_message("xingruiping@163.com", u"测试邮件标题3", u"这是一封来自UnitedStack的测试邮件", "default")
