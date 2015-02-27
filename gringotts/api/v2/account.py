import pecan
import wsme
import datetime

from pecan import rest
from pecan import request
from wsmeext.pecan import wsexpose
from wsme import types as wtypes

from oslo.config import cfg

from gringotts import master
from gringotts.api import acl
from gringotts.policy import check_policy
from gringotts import exception
from gringotts import utils as gringutils
from gringotts.api.v2 import models
from gringotts.db import models as db_models
from gringotts.services import keystone
from gringotts.checker import notifier
from gringotts.openstack.common import log
from gringotts.openstack.common import uuidutils
from gringotts.openstack.common import timeutils


cfg.CONF.import_opt('notifier_level', 'gringotts.checker.service', group='checker')
LOG = log.getLogger(__name__)


class AccountController(rest.RestController):
    """Manages operations on account
    """

    _custom_actions = {
        'level': ['PUT'],
        'charges': ['GET'],
        'estimate': ['GET'],
        'estimate_per_day': ['GET'],
        'invitees': ['GET'],
    }

    def __init__(self, user_id):
        self._id = user_id

    def _account(self):
        self.conn = pecan.request.db_conn
        try:
            account = self.conn.get_account(request.context, self._id)
        except Exception as e:
            LOG.error('account %s not found' % self._id)
            raise exception.AccountNotFound(user_id=self._id)
        return account

    @wsexpose(models.Invitees, int, int)
    def invitees(self, limit=None, offset=None):
        """Get invitees of inviter
        """
        inviter = acl.get_limited_to_user(request.headers) or self._id

        self.conn = pecan.request.db_conn
        try:
            _invitees, total_count = self.conn.get_invitees(request.context,
                                                            inviter,
                                                            limit=limit,
                                                            offset=offset)
        except Exception as e:
            LOG.exception('Fail to get invitees')
            raise exception.DBError(reason=e)

        invitees = []
        for invitee in _invitees:
            user = keystone.get_uos_user(invitee.user_id)
            if user:
                user_name = user.get('real_name') or user['email'].split('@')[0]
                user_email = user['email']
            else:
                user_name = ""
                user_email = ""
            invitees.append(models.Invitee(user_id=invitee.user_id,
                                           user_name=user_name,
                                           user_email=user_email,
                                           created_at=invitee.created_at,
                                           charged=invitee.charged,
                                           reward_value=invitee.reward_value))
        return models.Invitees(total_count=total_count,
                               invitees=invitees)

    @wsexpose(models.UserAccount, int)
    def level(self, level):

        check_policy(request.context, "account:level")

        if not isinstance(level, int) or level < 0 or level > 9:
            raise exception.InvalidParameterValue(err="Invalid Level")

        self.conn = pecan.request.db_conn
        try:
            account = self.conn.change_account_level(request.context, self._id, level)
        except Exception as e:
            LOG.exception('Fail to change the account level of: %s' % self._id)
            raise exception.DBError(reason=e)

        return models.UserAccount.from_db_model(account)

    @wsexpose(models.UserAccount)
    def get(self):
        """Return this product"""
        return models.UserAccount.from_db_model(self._account())

    @wsexpose(models.Charge, wtypes.text, body=models.Charge)
    def put(self, data):
        """Charge the account
        """
        check_policy(request.context, "account:charge")

        # Check the charge value
        if data.value < -100000 or data.value > 100000:
            raise exception.InvalidChargeValue(value=data.value)

        remarks = data.remarks if data.remarks != wsme.Unset else None
        operator=request.context.user_id

        self.conn = pecan.request.db_conn

        try:
            charge, is_first_charge = self.conn.update_account(request.context,
                                                               self._id,
                                                               operator=operator,
                                                               **data.as_dict())
            has_bonus = False
            if cfg.CONF.enable_bonus and data['type'] != 'bonus':
                value = gringutils.calculate_bonus(data['value'])
                if value > 0:
                    bonus, _ = self.conn.update_account(request.context,
                                                        self._id,
                                                        type='bonus',
                                                        value=value,
                                                        come_from='system',
                                                        operator=operator,
                                                        remarks=remarks)
                    has_bonus = True

            if cfg.CONF.enable_invitation and is_first_charge:
                _account = self._account()
                min_charge_value = gringutils._quantize_decimal(cfg.CONF.min_charge_value)
                reward_value = gringutils._quantize_decimal(cfg.CONF.reward_value)

                if _account.inviter and data.value >= min_charge_value and reward_value > 0:
                    self.conn.update_account(request.context,
                                             _account.inviter,
                                             type='bonus',
                                             value=reward_value,
                                             come_from='system',
                                             operator=operator,
                                             remarks="reward because of invitation",
                                             invitee=self._id)
                    if cfg.CONF.notify_account_charged:
                        inviter = self.conn.get_account(request.context, _account.inviter).as_dict()
                        contact = keystone.get_uos_user(inviter['user_id'])
                        self.notifier = notifier.NotifierService(cfg.CONF.checker.notifier_level)
                        self.notifier.notify_account_charged(request.context,
                                                             inviter,
                                                             contact,
                                                             'bonus',
                                                             reward_value,
                                                             bonus=0,
                                                             operator=operator,
                                                             operator_name=request.context.user_name,
                                                             remarks="reward because of invitation")
            self.conn.set_charged_orders(request.context, self._id)
        except exception.NotAuthorized as e:
            LOG.exception('Fail to charge the account:%s due to not authorization' % \
                          self._id)
            raise exception.NotAuthorized()
        except Exception as e:
            LOG.exception('Fail to charge the account:%s, charge value: %s' % \
                          (self._id, data.value))
            raise exception.DBError(reason=e)
        else:
            # Notifier account
            if cfg.CONF.notify_account_charged:
                account = self.conn.get_account(request.context, self._id).as_dict()
                contact = keystone.get_uos_user(account['user_id'])
                country_code = contact.get("country_code") or "86"
                language = "en_US" if country_code != '86' else "zh_CN"
                self.notifier = notifier.NotifierService(cfg.CONF.checker.notifier_level)
                self.notifier.notify_account_charged(request.context,
                                                     account,
                                                     contact,
                                                     data['type'],
                                                     charge.value,
                                                     bonus=bonus.value if has_bonus else 0,
                                                     operator=operator,
                                                     operator_name=request.context.user_name,
                                                     remarks=remarks,
                                                     language=language)
        return models.Charge.from_db_model(charge)

    @wsexpose(models.Charges, wtypes.text, datetime.datetime, datetime.datetime, int, int)
    def charges(self, type=None, start_time=None, end_time=None, limit=None, offset=None):
        """Return this account's charge records
        """
        self.conn = pecan.request.db_conn
        charges = self.conn.get_charges(request.context,
                                        user_id=self._id,
                                        type=type,
                                        limit=limit,
                                        offset=offset,
                                        start_time=start_time,
                                        end_time=end_time)
        charges_list = []
        for charge in charges:
            charges_list.append(models.Charge.from_db_model(charge))

        total_price, total_count = self.conn.get_charges_price_and_count(
            request.context, user_id=self._id, type=type,
            start_time=start_time, end_time=end_time)
        total_price = gringutils._quantize_decimal(total_price)

        return models.Charges.transform(total_price=total_price,
                                        total_count=total_count,
                                        charges=charges_list)

    @wsexpose(int)
    def estimate(self):
        self.conn = pecan.request.db_conn

        if not cfg.CONF.enable_owe:
            return -1

        account = self._account()
        if account.balance < 0:
            return -2

        orders = self.conn.get_active_orders(request.context,
                                             user_id=self._id,
                                             within_one_hour=True)
        if not orders:
            return -1

        price_per_hour = 0
        for order in orders:
            price_per_hour += gringutils._quantize_decimal(order.unit_price)

        if price_per_hour == 0:
            return -1

        price_per_day = price_per_hour * 24
        days_to_owe_d = float(account.balance / price_per_day)
        days_to_owe = round(days_to_owe_d)
        if days_to_owe < days_to_owe_d:
            days_to_owe = days_to_owe + 1
        if days_to_owe > 7:
            return -1
        return days_to_owe

    @wsexpose(models.Estimate)
    def estimate_per_day(self):
        self.conn = pecan.request.db_conn

        account = self._account()
        orders = self.conn.get_active_orders(request.context,
                                             user_id=self._id,
                                             within_one_hour=True)
        price_per_day = 0
        remaining_day = -1
        if not orders:
            return models.Estimate(price_per_day=price_per_day,
                                   remaining_day=remaining_day)

        price_per_hour = 0
        for order in orders:
            price_per_hour += gringutils._quantize_decimal(order.unit_price)

        if price_per_hour == 0:
            return models.Estimate(price_per_day=price_per_day,
                                   remaining_day=remaining_day)

        price_per_day = price_per_hour * 24
        remaining_day = int(account.balance / price_per_day)

        return models.Estimate(price_per_day=price_per_day,
                               remaining_day=remaining_day)


class ChargeController(rest.RestController):

    @wsexpose(models.Charges, wtypes.text, datetime.datetime, datetime.datetime, int, int)
    def get(self, type=None, start_time=None, end_time=None, limit=None, offset=None):
        """Get all charges of all account
        """
        check_policy(request.context, "charges:all")

        users = {}
        def _get_user(user_id):
            user = users.get(user_id)
            if user:
                return user
            contact = keystone.get_uos_user(user_id)
            user_name = contact['name'] if contact else None
            users[user_id] = models.User(user_id=user_id,
                                         user_name=user_name)
            return users[user_id]

        self.conn = pecan.request.db_conn
        charges = self.conn.get_charges(request.context,
                                        type=type,
                                        limit=limit,
                                        offset=offset,
                                        start_time=start_time,
                                        end_time=end_time)
        charges_list = []
        for charge in charges:
            acharge = models.Charge.from_db_model(charge)
            acharge.actor = _get_user(charge.operator)
            acharge.target = _get_user(charge.user_id)
            charges_list.append(acharge)

        total_price, total_count = self.conn.get_charges_price_and_count(
            request.context, type=type, start_time=start_time, end_time=end_time)
        total_price = gringutils._quantize_decimal(total_price)

        return models.Charges.transform(total_price=total_price,
                                        total_count=total_count,
                                        charges=charges_list)


class AccountsController(rest.RestController):
    """Manages operations on the accounts collection
    """

    charges = ChargeController()

    @pecan.expose()
    def _lookup(self, user_id, *remainder):
        if remainder and not remainder[-1]:
            remainder = remainder[:-1]
        if len(user_id) == 32:
            return AccountController(user_id), remainder

    @wsexpose(models.AdminAccounts, bool, int, int)
    def get_all(self, owed=None, limit=None, offset=None):
        """Get all accounts
        """
        self.conn = pecan.request.db_conn

        try:
            accounts = self.conn.get_accounts(request.context, owed=owed,
                                              limit=limit, offset=offset)
            count = self.conn.get_accounts_count(request.context, owed=owed)
            pecan.response.headers['X-Total-Count'] = str(count)
        except exception.NotAuthorized as e:
            LOG.exception('Fail to get all accounts')
            raise exception.NotAuthorized()
        except Exception as e:
            LOG.exception('Fail to get all accounts')
            raise exception.DBError(reason=e)

        accounts = [models.AdminAccount.from_db_model(account)
                    for account in accounts]

        return models.AdminAccounts(total_count=count,
                                    accounts=accounts)


    @wsexpose(None, body=models.AdminAccount)
    def post(self, data):
        """Create a new account
        """
        conn = pecan.request.db_conn
        try:
            account = db_models.Account(**data.as_dict())
            return conn.create_account(request.context, account)
        except Exception:
            LOG.exception('Fail to create account: %s' % data.as_dict())
            raise exception.AccountCreateFailed(user_id=data.user_id,
                                                domain_id=data.domain_id)
