
import pecan
from pecan import rest
from wsmeext.pecan import wsexpose

from gringotts.api import acl
from gringotts.api.v2 import models
from gringotts import exception
from gringotts.openstack.common import log as logging
from gringotts import policy
from gringotts.services import keystone

LOG = logging.getLogger(__name__)


class SalesPersonAccountsController(rest.RestController):

    def __init__(self, sales_id):
        self.sales_id = sales_id

    @wsexpose(models.SalesPersonAccounts, int, int)
    def get(self, offset=None, limit=None):
        """Get the accounts of this sales person
        """
        context = pecan.request.context
        if not acl.limit_to_sales(context, self.sales_id):
            raise exception.NotAuthorized()

        conn = pecan.request.db_conn
        accounts_number, sales_amount = conn.get_salesperson_amount(
            context, self.sales_id)
        accounts = conn.get_salesperson_customer_accounts(
            context, self.sales_id, offset, limit)
        account_list = []
        for account in accounts:
            user = keystone.get_uos_user(account.user_id)
            account_list.append(
                models.SalesPersonAccount(
                    user_id=account.user_id,
                    user_name=user['name'],
                    user_email=user.get('email', ''),
                    real_name=user.get('real_name', ''),
                    mobile_number=user.get('mobile_number', ''),
                    company=user.get('company', ''),
                    balance=account.balance,
                    consumption=account.consumption,
                    owed=account.owed
                )
            )

        return models.SalesPersonAccounts(
            total_count=accounts_number, accounts=account_list)

    @wsexpose(None, body=models.SalesPersonAccountsPutBody)
    def put(self, data):
        context = pecan.request.context
        policy.check_policy(context, 'uos_sales_admin')

        conn = pecan.request.db_conn
        conn.set_accounts_salesperson(context, data.user_ids, self.sales_id)


class SalesPersonController(rest.RestController):
    """Controller of a sales person
    """

    _custom_actions = {
        'amount': ['GET'],
    }

    def __init__(self, sales_id):
        self.sales_id = sales_id

    @pecan.expose()
    def _lookup(self, subpath, *remainder):
        if subpath == 'accounts':
            return SalesPersonAccountsController(
                self.sales_id), remainder

    @wsexpose(models.SalesPersonAmount)
    def amount(self):
        """Get the sales amount of this sales person
        """
        context = pecan.request.context
        if not acl.limit_to_sales(context, self.sales_id):
            raise exception.NotAuthorized()

        conn = pecan.request.db_conn
        accounts_number, sales_amount = conn.get_salesperson_amount(
            context, self.sales_id)
        return models.SalesPersonAmount(
            sales_amount=sales_amount, accounts_number=accounts_number)


class SalesPersonsController(rest.RestController):
    """Controller of sales persons
    """

    @pecan.expose()
    def _lookup(self, sales_id, *remainder):
        return SalesPersonController(sales_id), remainder
