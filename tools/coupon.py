import sys
import json
import requests
from gringotts.client import client

OS_AUHT_URL = 'http://localhost:35357/v3'

client = client.Client(username='admin',
                       password='rachel',
                       project_name='admin',
                       auth_url=OS_AUHT_URL)


def generate_coupons(number, price):
    body = dict(number=number,
                price=price)
    client.post('/precharge', body=body)


def get_coupons(remarks=None):
    __, precharges = client.get('/precharge')

    codes = []

    for precharge in precharges:
        if precharge['used'] or precharge['dispatched']:
            continue
        code = precharge['code']

        dispatch_coupon(code, remarks)

        code = "%s-%s-%s-%s" % (code[0:4], code[4:8], code[8:12], code[12:16])
        print code, precharge['price']


def dispatch_coupon(code, remarks):
    if remarks:
        _body = dict(remarks=remarks)
        client.put('/precharge/%s/dispatched' % code, body=_body)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print 'usage: python coupon.py <number> <price> [remarks]'
        sys.exit()

    number = sys.argv[1]

    try:
        int(sys.argv[1])
    except ValueError:
        sys.exit("Invalid number, should be an number")

    if int(sys.argv[1]) < 0:
        sys.exit("Invalid number, should be greater than 0")

    price = sys.argv[2]
    try:
        remarks = sys.argv[3]
    except IndexError:
        remarks = None

    generate_coupons(number, price)
    get_coupons(remarks)
