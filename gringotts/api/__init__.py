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

OPTS = [
    cfg.BoolOpt('enable_bonus',
               default=False,
               help='Enable bouns or not'),
    cfg.BoolOpt('notify_account_charged',
                default=False,
                help="Notify user when he/she charges"),
    cfg.StrOpt('precharge_limit_rule',
               default='5/quarter',
               help='Frequency of do precharge limitation'),
    cfg.ListOpt('regions',
                default=['RegionOne'],
                help="A list of regions that is avaliable")
]

CONF = cfg.CONF
CONF.register_opts(OPTS)
