import pecan
from pecan import rest
from pecan import request
from wsmeext.pecan import wsexpose
from wsme import types as wtypes

from oslo.config import cfg

from gringotts.policy import check_policy
from gringotts import exception
from gringotts.api.v2 import models
from gringotts.db import models as db_models
from gringotts.openstack.common import log
from gringotts.services import keystone

LOG = log.getLogger(__name__)


class SalesAccountsController(rest.RestController):
    """Manages operations on sales and accounts. usually sales:account=1:n
    """

    _custom_actions = {
        'add_account_sales': ['POST'],
        'add_accounts_sales': ['POST'],
        'get_sales_accounts': ['GET'],
        'update_account_sales': ['PUT'],
        'update_accounts_sales': ['PUT'],
    }

    @wsexpose(None, wtypes.text, wtypes.text)
    def add_account_sales(self, account_id, sales_id):
        """assign a account to a sales
        """
        check_policy(request.context, "sales:add_account_sales")

        sales = keystone.get_uos_user(sales_id)
        if not sales:
            LOG.warning('sales_id: %s do not exist.' % sales_id)
            raise exception.SalesIdNotFound(sales_id)

        conn = pecan.request.db_conn
        conn.add_account_sales(account_id, sales_id)

    @wsexpose(None, body=models.AccountsSales)
    def add_accounts_sales(self, data):
        """assign many accounts to a sales
        """
        check_policy(request.context, "sales:add_accounts_sales")

        sales = keystone.get_uos_user(data.sales_id)
        if not sales:
            LOG.warning('sales_id: %s do not exist.' % data.sales_id)
            raise exception.SalesIdNotFound(data.sales_id)

        conn = pecan.request.db_conn
        conn.add_accounts_sales(data)

    @wsexpose(models.AdminAccounts, wtypes.text, int, int)
    def get_sales_accounts(self, sales_id, limit=None, offset=None):
        """get all accounts that belong to a salesman
        """
        check_policy(request.context, "sales:get_sales_accounts")

        sales = keystone.get_uos_user(sales_id)
        if not sales:
            LOG.warning('sales_id: %s do not exist.' % sales_id)
            raise exception.SalesIdNotFound(sales_id)

        self.conn = pecan.request.db_conn
        try:
            accounts = self.conn.get_accounts_by_sales(request.context,
                                                       sales_id,
                                                       limit=limit,
                                                       offset=offset)
            accounts = [models.AdminAccount.from_db_model(account)
                        for account in accounts]
            count = self.conn.get_accounts_by_sales_count(request.context,
                                                          sales_id)
        except exception.NotAuthorized as e:
            LOG.exception('Failed to get all accounts that assigned to salesman %s'
                % sales_id)
            raise exception.NotAuthorized()
        except Exception as e:
            LOG.exception(e)

        return models.AdminAccounts(total_count=count, accounts=accounts)

    @wsexpose(None, wtypes.text, wtypes.text)
    def update_account_sales(self, account_id, new_sales_id):
        """update a account's sales
        """
        check_policy(request.context, "sales:update_account_sales")

        sales = keystone.get_uos_user(new_sales_id)
        if not sales:
            LOG.warning('sales_id: %s do not exist.' % new_sales_id)
            raise exception.SalesIdNotFound(new_sales_id)

        conn = pecan.request.db_conn
        conn.update_account_sales(account_id, new_sales_id)

    @wsexpose(None, wtypes.text, wtypes.text)
    def update_accounts_sales(self, old_sales_id, new_sales_id):
        """update accounts' sales
        """
        check_policy(request.context, "sales:update_accounts_sales")

        sales = keystone.get_uos_user(new_sales_id)
        if not sales:
            LOG.warning('sales_id: %s do not exist.' % new_sales_id)
            raise exception.SalesIdNotFound(new_sales_id)

        conn = pecan.request.db_conn
        conn.update_accounts_sales(old_sales_id, new_sales_id)
