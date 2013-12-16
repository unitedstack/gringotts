from oslo.config import cfg

from gringotts.worker import api as worker_api


def API(*args, **kwargs):
    use_local = kwargs.pop('use_local', False)
    if cfg.CONF.worker.use_local or use_local:
        api = worker_api.LocalAPI
    else:
        api = worker_api.API
    return api(*args, **kwargs)
