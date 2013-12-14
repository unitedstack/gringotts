from oslo.config import cfg

# Register options for the service
API_SERVICE_OPTS = [
    cfg.IntOpt('port',
               default=8975,
               help='The port for the gringotts API server',
               ),
    cfg.StrOpt('host',
               default='0.0.0.0',
               help='The listen IP for the gringotts API server',
               ),
]

CONF = cfg.CONF
opt_group = cfg.OptGroup(name='api',
                         title='Options for the gring-api service')
CONF.register_group(opt_group)
CONF.register_opts(API_SERVICE_OPTS, opt_group)
