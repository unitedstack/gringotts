import eventlet
eventlet.monkey_patch()

import os
import sys
import pecan

from oslo_config import cfg
from paste import deploy

from gringotts import db
from gringotts.api import config
from gringotts.api import hooks
from gringotts.api import middleware
from gringotts.client.v2 import client


OPTS = [
    cfg.StrOpt('api_paste_config',
               default="api_paste.ini",
               help="Configuration file for WSGI definition of API."
               ),
]
CONF = cfg.CONF
CONF.register_opts(OPTS)


EXT_OPTS = [
    cfg.BoolOpt('enable',
                default=False,
                help="Use external billing system or not"),
    cfg.StrOpt('cacert',
               help="The path to a bundle or CA certs to check against"),
    cfg.StrOpt('auth_plugin',
               default='token',
               help="which auth plugin to use to authticate the client"),
]

SIGN_OPTS = [
    cfg.StrOpt('access_key_id',
               help="access_key_id will be used if auth_method is sign"),
    cfg.StrOpt('access_key',
               help="access_key will be used if auth_method is sign"),
    cfg.StrOpt('sign_type',
               default='MD5',
               help="The digest signature algorithm"),
    cfg.StrOpt('endpoint',
               default="http://localhost:8976/v2",
               help="The external billing system endpoint"),
]

TOKEN_OPTS = [
    cfg.StrOpt('username',
               default='admin',
               help='Username to use for openstack service access'),
    cfg.StrOpt('password',
               default='admin',
               help='Password to use for openstack service access'),
    cfg.StrOpt('project_name',
               default='admin',
               help='Tenant name to use for openstack service access'),
    cfg.StrOpt('user_domain_name',
               default='Default',
               help='user domain name'),
    cfg.StrOpt('project_domain_name',
               default='Default',
               help='project domain name'),
    cfg.StrOpt('auth_url',
               default='http://localhost:35357/v3',
               help='Auth URL to use for external openstack service access'),
    cfg.StrOpt('service_type',
               default='billing',
               help="The service type to determine which endpoint to use")
]

cfg.CONF.register_opts(EXT_OPTS, group="external_billing")
cfg.CONF.register_opts(SIGN_OPTS, group="sign")
cfg.CONF.register_opts(TOKEN_OPTS, group="token")


def _external_token_client(verify=True):
    token = cfg.CONF.token
    return client.Client(auth_plugin='token',
                         verify=verify,
                         user_domain_name=token.user_domain_name,
                         username=token.username,
                         password=token.password,
                         project_domain_name=token.project_domain_name,
                         project_name=token.project_name,
                         auth_url=token.auth_url,
                         service_type=token.service_type)


def _external_sign_client(verify=True):
    sign = cfg.CONF.sign
    return client.Client(auth_plugin='sign',
                         verify=verify,
                         access_key_id=sign.access_key_id,
                         access_key=sign.access_key,
                         sign_type=sign.sign_type,
                         endpoint=sign.endpoint)


def external_client():
    if not cfg.CONF.external_billing.enable:
        return

    verify = True
    if cfg.CONF.external_billing.cacert:
        verify = cfg.CONF.external_billing.cacert

    auth_plugin = cfg.CONF.external_billing.auth_plugin
    method = getattr(sys.modules[__name__], "_external_%s_client" % auth_plugin)
    if method:
        return method(verify=verify)


def get_pecan_config():
    """Get the pecan configuration."""
    filename = config.__file__.replace('.pyc', '.py')
    return pecan.configuration.conf_from_file(filename)


def setup_app(config=None):

    app_hooks = [hooks.ConfigHook(),
                 hooks.DBHook(db.get_connection(CONF)),
                 hooks.ContextHook(),
                 hooks.LimitHook()]

    if not config:
        config = get_pecan_config()

    app = pecan.make_app(
        config.app.root,
        static_root=config.app.static_root,
        template_path=config.app.template_path,
        debug=False,
        force_canonical=getattr(config.app, 'force_canonical', True),
        hooks=app_hooks,
        wrap_app=middleware.FaultWrapperMiddleware,
    )

    pecan.conf.update({'wsme': {'debug': CONF.debug}})

    return app


def load_app():
    # Build the WSGI app
    cfg_file = None
    cfg_path = cfg.CONF.api_paste_config
    if not os.path.isabs(cfg_path):
        cfg_file = CONF.find_file(cfg_path)
    elif os.path.exists(cfg_path):
        cfg_file = cfg_path

    if not cfg_file:
        raise cfg.ConfigFilesNotFoundError([cfg.CONF.api_paste_config])
    return deploy.loadapp("config:" + cfg_file)


def app_factory(global_config, **local_conf):
    return setup_app()
