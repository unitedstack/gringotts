import pecan
import wsme
import datetime

from pecan import rest
from pecan import request
from wsmeext.pecan import wsexpose
from wsme import types as wtypes

from oslo.config import cfg

from gringotts import exception
from gringotts import utils as gringutils
from gringotts.api.v1 import models
from gringotts.db import models as db_models
from gringotts.openstack.common import log
from gringotts.openstack.common import uuidutils
from gringotts.openstack.common import timeutils


LOG = log.getLogger(__name__)


class AccountController(rest.RestController):
    """Manages operations on account
    """

    _custom_actions = {
        'charges': ['GET'],
    }

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

    @wsexpose(models.UserAccount)
    def get(self):
        """Return this product"""
        return models.UserAccount.from_db_model(self._account())

    @wsexpose(models.Charge, wtypes.text, body=models.Charge)
    def put(self, data):
        """Charge the account
        """
        # check the charge value
        if not data.value or data.value < 0:
            raise exception.InvalidChargeValue(value=data.value)

        self.conn = pecan.request.db_conn

        # update account
        account = self._account()
        try:
            account.balance += data.value
            self.conn.update_account(request.context, account)
        except exception.NotAuthorized as e:
            LOG.exception('Fail to charge the account:%s due to not authorization' % \
                          self._id)
            raise exception.NotAuthorized()
        except Exception as e:
            LOG.exception('Fail to charge the account:%s, charge value: %s' % \
                          (self._id, data.value))
            raise exception.DBError(reason=e)

        # Create a charge record
        if not data.charge_time:
            charge_time = datetime.datetime.utcnow()
        else:
            charge_time = timeutils.parse_isotime(data.charge_time)
        try:
            charge_in = db_models.Charge(charge_id=uuidutils.generate_uuid(),
                                         project_id=self._id,
                                         currency='CNY',
                                         value=data.value,
                                         type=data.type or None,
                                         come_from=data.come_from or None,
                                         charge_time=charge_time)
            charge = self.conn.create_charge(request.context, charge_in)
        except exception.NotAuthorized as e:
            LOG.exception('Fail to charge the account:%s due to not authorization' % \
                          self._id)
            raise exception.NotAuthorized()
        except TypeError as e:
            error = 'Error while turning charge: %s' % data.as_dict()
            LOG.exception(error)
            raise exception.MissingRequiredParams(reason=error)
        except Exception as e:
            error = 'Error while creating charge: %s' % data.as_dict()
            LOG.exception(error)
            raise exception.DBError(reason=error)

        charge.value = gringutils._quantize_decimal(charge.value)

        return models.Charge.from_db_model(charge)

    @wsexpose(models.Charges, datetime.datetime, datetime.datetime, int, int)
    def charges(self, start_time=None, end_time=None, limit=None, offset=None):
        """Return this account's charge records
        """
        self.conn = pecan.request.db_conn
        charges = self.conn.get_charges(request.context,
                                        limit=limit,
                                        offset=offset,
                                        start_time=start_time,
                                        end_time=end_time)
        charges_list = []
        for charge in charges:
            charges_list.append(models.Charge.from_db_model(charge))

        total_price, total_count = self.conn.get_charges_price_and_count(
            request.context, start_time=start_time, end_time=end_time)
        total_price = gringutils._quantize_decimal(total_price)

        return models.Charges.transform(total_price=total_price,
                                        total_count=total_count,
                                        charges=charges_list)


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
        """Get all account
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
