import pecan
import wsme
import datetime

from pecan import rest
from pecan import request
from wsmeext.pecan import wsexpose
from wsme import types as wtypes

from oslo.config import cfg

from gringotts import exception
from gringotts.api.v1 import models
from gringotts.db import models as db_models
from gringotts.openstack.common import log
from gringotts.openstack.common import uuidutils


LOG = log.getLogger(__name__)


class AccountController(rest.RestController):
    """Manages operations on account
    """

    def __init__(self, project_id):
        pecan.request.context['project_id'] = project_id
        self._id = project_id

    def _account(self):
        self.conn = pecan.request.db_conn
        try:
            account = self.conn.get_account(request.context,
                                            project_id=self._id)
        except Exception as e:
            LOG.error('account %s not found' % self._id)
            raise exception.AccountNotFound(project_id=self._id)
        return account

    @wsexpose(models.UserAccount, wtypes.text)
    def get(self):
        """Return this product"""
        return models.UserAccount.from_db_model(self._account())


class AccountsController(rest.RestController):
    """Manages operations on the accounts collection
    """
    @pecan.expose()
    def _lookup(self, project_id, *remainder):
        if remainder and not remainder[-1]:
            remainder = remainder[:-1]
        return AccountController(project_id), remainder

    @wsexpose([models.AdminAccount])
    def get_all(self):
        """Get all product
        """
        self.conn = pecan.request.db_conn

        try:
            accounts = self.conn.get_accounts(request.context)
        except exception.NotAuthorized as e:
            LOG.exception('Fail to get all accounts')
            raise exception.NotAuthorized()
        except Exception as e:
            LOG.exception('Fail to get all accounts')
            raise exception.DBError(reason=e)

        return [models.AdminAccount.from_db_model(account)
                for account in accounts]
