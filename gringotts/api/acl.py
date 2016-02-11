from gringotts.openstack.common import policy
from oslo_config import cfg


_ENFORCER = None

def get_enforcer():
    global _ENFORCER
    if not _ENFORCER:
        _ENFORCER = policy.Enforcer()
    return _ENFORCER


def get_limited_to(headers, action):
    """Return the user and project the request should be limited to.

    :param headers: HTTP headers dictionary
    :return: A tuple of (user, project), set to None if there's no limit on
    one of these.
    """
    _ENFORCER = get_enforcer()
    if not _ENFORCER.enforce(action,
                             {},
                             {'roles': headers.get('X-Roles', "").split(",")}):
        return headers.get('X-User-Id'), headers.get('X-Project-Id')
    return None, None


def get_limited_to_user(headers, action):
    return get_limited_to(headers, action)[0]


def get_limited_to_project(headers, action):
    return get_limited_to(headers, action)[1]


def limit_to_sales(context, user_id):
    """Limit permission via sales related roles.

    If roles of context matched rule uos_sales_admin, return True.
    If roles of context matched rule uos_sales but not uos_sales_admin,
    return True if context.user_id matched user_id, or False.
    Otherwise, return False.
    """

    _ENFORCER = get_enforcer()
    context_dict = context.to_dict()
    if _ENFORCER.enforce('uos_sales_admin', {}, context_dict):
        return True

    if _ENFORCER.enforce('uos_sales', {}, context_dict):
        return context.user_id == user_id

    return False


def context_is_admin(headers):
    """Check whether the context is admin or not."""
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
    """Check whether the context is domain owner or not."""
    global _ENFORCER
    if not _ENFORCER:
        _ENFORCER = policy.Enforcer()
    if not _ENFORCER.enforce('context_is_domain_owner',
                             {},
                             {'roles': headers.get('X-Roles', "").split(",")}):
        return False
    else:
        return True
