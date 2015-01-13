"""
Signature auth method
"""
import types
import hashlib
from gringotts.client.auth import BaseAuthPlugin


def smart_str(s, encoding='utf-8', strings_only=False, errors='strict'):
    """
    Returns a bytestring version of 's', encoded as specified in 'encoding'.

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
                return ' '.join([smart_str(arg, encoding, strings_only,
                        errors) for arg in s])
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
def build_sign(prestr, key, sign_type = 'MD5'):
    if sign_type == 'MD5':
        return hashlib.md5(prestr + key).hexdigest()
    return ''


class SignAuthPlugin(BaseAuthPlugin):
    """Caculate the signature

    The signature algorithm fllows the aliapay direct pay signature method,
    which signs the params and body using MD5 digest algorithm.
    """

    def __init__(self,
                 access_key_id=None,
                 access_key=None,
                 sign_type='MD5',
                 endpoint=None):
        self.access_key_id = access_key_id
        self.access_key = access_key
        self.sign_type = sign_type
        self.endpoint = endpoint

    def get_auth_headers(self, **kwargs):
        params = kwargs.get('params') or {}
        body = kwargs.get('data') or ""

        sign_str = build_sign_str(params, body)
        sign = build_sign(sign_str, self.access_key, self.sign_type)

        auth = dict(access_key_id=self.access_key_id,
                    sign_type=self.sign_type,
                    sign=sign)
        return auth

    def get_endpoint(self):
        return self.endpoint

    def filter_params(self, params):
        ks = params.keys()
        ks.sort()
        newparams = {}
        for k in ks:
            v = params[k]
            k = smart_str(k)
            if k not in ('sign','sign_type') and v != '' and v != None:
                newparams[k] = smart_str(v)
        return newparams
