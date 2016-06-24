import pecan                                                                                              
import wsme                                                                                               
                                                                                                          
from pecan import rest                                                                                    
from pecan import request                                                                                 
from wsmeext.pecan import wsexpose                                                                        
from wsme import types as wtypes                                                                          
                                                                                                          
from oslo_config import cfg                                                                               
                                                                                                          
from gringotts.api.v2 import models                                                                       
from gringotts.db import models as db_models                                                              
from gringotts.openstack.common import log                                                                
from gringotts import utils as gringutils                                                                 
from gringotts import exception
                                                                                                          
                                                                                                          
LOG = log.getLogger(__name__)


class AccountsController(rest.RestController):
    """Manages operations on the accounts collection."""

    @wsexpose(None, body=models.AdminAccount)
    def post(self, data):
        """Create a new account."""
        conn = pecan.request.db_conn
        try:
            account = db_models.Account(**data.as_dict())
            return conn.create_account(request.context, account)
        except Exception:
            LOG.exception('Fail to create account: %s' % data.as_dict())
            raise exception.AccountCreateFailed(user_id=data.user_id,
                                                domain_id=data.domain_id)
