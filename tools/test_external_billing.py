# coding: utf-8

import json
import hashlib
import requests
import types

access_key_id = "84"
access_key = "E7EFH8FNQOI3Q489ASDFJAS78RWGHREF"
sign_type = "MD5"
endpoint = "http://api.gotcy.com/accounting"


def smart_str(s, encoding='utf-8', strings_only=False, errors='strict'):
    """Returns a bytestring version of 's', encoded as specified in 'encoding'.

    If strings_only is True, don't convert (some) non-string-like objects.
    """
    if strings_only and isinstance(s, (types.NoneType, int)):
        return s
    if not isinstance(s, basestring):
        try:
            return str(s)
        except UnicodeEncodeError:
            if isinstance(s, Exception):
                # An Exception subclass containing non-ASCII data that doesn't
                # know how to print itself properly. We shouldn't raise a
                # further exception.
                return ' '.join([smart_str(arg, encoding, strings_only, errors)
                                 for arg in s])
            return unicode(s).encode(encoding, errors)
    elif isinstance(s, unicode):
        return s.encode(encoding, errors)
    elif s and encoding != 'utf-8':
        return s.decode('utf-8', errors).encode(encoding, errors)
    else:
        return s


def build_sign_str(params, body):
    ks = params.keys()
    prestr = ''
    for k in ks:
        v = params[k]
        prestr += '%s=%s&' % (k, v)
    prestr = prestr[:-1] + "\n" + body + "\n"
    return prestr


# generate the sign
def build_sign(prestr, key, sign_type='MD5'):
    if sign_type == 'MD5':
        return hashlib.md5(prestr + key).hexdigest()
    return ''


def get_user_balance(user_id, endpoint):

    params = dict(accountNum=user_id)

    sign_str = build_sign_str(params, "")
    sign = build_sign(sign_str, access_key, sign_type)

    headers = {"access_key_id": access_key_id,
               "sign_type": sign_type,
               "sign": sign}

    endpoint = endpoint + "/getBalance"
    response = requests.get(endpoint, headers=headers, params=params, verify=False)
    return response.content


def deduct_user_balance(user_id, endpoint, money):
    extData = {"resource_id": "fake_resource_id",
               "resource_name": "fake_resource_name",
               "resource_type": "fake_resource_type",
               "region_id": "fake_region_id",
               "order_id": "fake_order_id"}
    _body = {"reqId": 'fake_req_id_15',
             "accountNum": user_id,
             "money":  money,
             "type": '1',
             "remark": 'come from ustack',
             "extData": extData}
    # NOTE(suo): Must format body to json format, some languages only
    # accept standard josn, for example php only accept double quote
    # string in json.
    _body = json.dumps(_body)

    sign_str = build_sign_str({}, _body)
    sign = build_sign(sign_str, access_key, sign_type)

    headers = {"access_key_id": "%s" % access_key_id,
               "Content-Type": "application/json",
               "sign_type": "%s" % sign_type,
               "sign": "%s" % sign}

    endpoint = endpoint + "/pay"
    response = requests.put(endpoint, headers=headers, data=_body, verify=False)
    return response.content


def check_deduct_result(req_id, endpoint):
    params = dict(reqId=req_id)

    sign_str = build_sign_str(params, "")
    sign = build_sign(sign_str, access_key, sign_type)

    headers = {"access_key_id": access_key_id,
               "sign_type": sign_type,
               "sign": sign}

    endpoint = endpoint + "/checkReq"
    response = requests.get(endpoint, headers=headers, params=params, verify=False)
    return response.content

#print get_user_balance("a6d0ffb0c56f420ebc4711365dfda00f", endpoint)
#print deduct_user_balance("a6d0ffb0c56f420ebc4711365dfda00f", endpoint, '0.005')
#print check_deduct_result("test_req_id", endpoint)

#print get_user_balance("28e16f9781694b608ffdeb52c58702d3", endpoint)
#print deduct_user_balance("28e16f9781694b608ffdeb52c58702d3", endpoint, '0.0008')
print check_deduct_result("fake_req_id_15", endpoint)
