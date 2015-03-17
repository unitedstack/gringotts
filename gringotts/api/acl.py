from gringotts.openstack.common import policy
from keystoneclient.middleware import auth_token
from oslo.config import cfg


_ENFORCER = None
OPT_GROUP_NAME = 'keystone_authtoken'


def register_opts(conf):
    """Register keystoneclient middleware options
    """
    conf.register_opts(auth_token.opts,
                       group=OPT_GROUP_NAME)
    auth_token.CONF = conf


register_opts(cfg.CONF)


def install(app, conf):
    """Install ACL check on application."""
    return auth_token.AuthProtocol(app,
                                   conf=dict(conf.get(OPT_GROUP_NAME)))


def get_limited_to(headers, action):
    """Return the user and project the request should be limited to.

    :param headers: HTTP headers dictionary
    :return: A tuple of (user, project), set to None if there's no limit on
    one of these.

    """
    global _ENFORCER
    if not _ENFORCER:
        _ENFORCER = policy.Enforcer()
    if not _ENFORCER.enforce(action,
                             {},
                             {'roles': headers.get('X-Roles', "").split(",")}):
        return headers.get('X-User-Id'), headers.get('X-Project-Id')
    return None, None


def get_limited_to_user(headers, action):
    return get_limited_to(headers, action)[0]


def get_limited_to_project(headers, action):
    return get_limited_to(headers, action)[1]


def context_is_admin(headers):
    """Check if the context is admin"""
    global _ENFORCER
    if not _ENFORCER:
        _ENFORCER = policy.Enforcer()
    if not _ENFORCER.enforce('context_is_admin',
                             {},
                             {'roles': headers.get('X-Roles', "").split(",")}):
        return False
    else:
        return True


def context_is_domain_owner(headers):
    """Check if the context is domain owner"""
    global _ENFORCER
    if not _ENFORCER:
        _ENFORCER = policy.Enforcer()
    if not _ENFORCER.enforce('context_is_domain_owner',
                             {},
                             {'roles': headers.get('X-Roles', "").split(",")}):
        return False
    else:
        return True
