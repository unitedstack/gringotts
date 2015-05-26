#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json

import requests
from oslo.config import cfg

from gringotts.openstack.common import log
from gringotts.services import keystone
from gringotts.services import wrap_exception


LOG = log.getLogger(__name__)


OPTS = [
    cfg.StrOpt('lotus_endpoint', default=None,
               help='Lotus service URL.'),
]

cfg.CONF.register_opts(OPTS)


_lotus_client = None


def lotus_client():
    global _lotus_client
    if _lotus_client:
        return _lotus_client
    else:
        s = requests.Session()
        _lotus_client = s
        return s


def request_to_lotus(method, api_url, body=None, headers=None):
    service_url = cfg.CONF.lotus_endpoint
    if not service_url:
        return

    auth_token = keystone.get_token()
    client = lotus_client()
    if headers:
        client.headers.update(headers)
    client.headers.update({'X-Auth-Token': auth_token})
    client.request(method,
                   service_url.rstrip('/') + api_url,
                   data=body)


@wrap_exception()
def send_email(receivers, subject, content):
    email_api = '/publish/publish_email'
    body = {
        'subject': subject,
        'content': content,
    }
    for to in receivers:
        body.update(to=to)
        request_to_lotus('POST', email_api,
                         body=json.dumps(body),
                         headers={'Content-Type': 'application/json'})


def send_notification_email(subject, content):
    if not subject or not content:
        return

    receivers = cfg.CONF.notification_email_receivers
    if not receivers:
        return
    send_email(receivers, subject, content)
