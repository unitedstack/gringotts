
from oslo_config import cfg

from gringotts.db import api as db_api
from gringotts.openstack.common import log
from gringotts import service


LOG = log.getLogger(__name__)

def main():
    service.prepare_service()
    api = db_api.get_instance()
    api.upgrade()
