from oslo_config import cfg

from gringotts.master import api as master_api


def API(*args, **kwargs):
    use_local = kwargs.pop('use_local', False)
    if cfg.CONF.master.use_local or use_local:
        api = master_api.LocalAPI
    else:
        api = master_api.API
    return api(*args, **kwargs)
