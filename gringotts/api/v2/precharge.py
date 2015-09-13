import wsme
import pecan
import datetime

from oslo.config import cfg
from pecan import rest
from wsmeext.pecan import wsexpose
from wsme import types as wtypes

from gringotts import exception
from gringotts import utils
from gringotts.api.v2 import models
from gringotts.checker import notifier
from gringotts.services import keystone
from gringotts.openstack.common import memorycache
from gringotts.openstack.common import log
from gringotts.policy import check_policy


LOG = log.getLogger(__name__)
MC = None


def _get_cache():
    global MC
    if MC is None:
        MC = memorycache.get_client()
    return MC


class PrechargeController(rest.RestController):
    """Manage operations on a single precharge."""

    _custom_actions = {
        'dispatched': ['PUT'],
        'used': ['PUT'],
    }

    def __init__(self, code):
        self.code = code

    def _precharge(self):
        conn = pecan.request.db_conn
        try:
            precharge = conn.get_precharge_by_code(pecan.request.context,
                                                   code=self.code)
        except Exception:
            LOG.error('Precharge(%s) not found' % self.code)
            raise exception.PreChargeNotFound(precharge_code=self.code)
        return precharge

    @wsexpose(models.PreCharge)
    def get(self):
        return models.PreCharge.from_db_model(self._precharge())

    @wsexpose(None, wtypes.text, status_code=204)
    def delete(self):
        """Delete the precharge. Actually set the deleted status as True"""
        conn = pecan.request.db_conn
        context = pecan.request.context
        check_policy(context, "account:precharge")

        try:
            conn.delete_precharge(context, self.code)
        except exception.PreChargeNotFound:
            raise
        except Exception as e:
            msg = 'Failed to delete precharge:%s, for reason:%s' % \
                (self.code, e)
            LOG.error(msg)
            raise exception.PreChargeException()

    @wsexpose(models.PreCharge, wtypes.text,
              body=models.PreChargeDispatchedBody)
    def dispatched(self, data):
        conn = pecan.request.db_conn
        context = pecan.request.context
        check_policy(context, "account:precharge")

        if data.remarks == wsme.Unset:
            data.remarks = None

        try:
            precharge = conn.dispatch_precharge(context,
                                                self.code,
                                                remarks=data.remarks)
        except exception.PreChargeNotFound:
            LOG.error('The precharge %s not found' % self.code)
            raise exception.PreChargeNotFound(precharge_code=self.code)
        except Exception as e:
            LOG.error('Fail to dispatch precharge(%s), for reason: %s' %
                      (self.code, e))
            raise exception.PreChargeException()

        return models.PreCharge.from_db_model(precharge)

    def _parse_limit_rule(self, rule):
        max_count, unit = rule.split('/')
        if unit == 'm':
            cache_time = 60
        if unit == 'quarter':
            cache_time = 60 * 15
        if unit == 'h':
            cache_time = 60 * 60
        if unit == 'd':
            cache_time = 60 * 60 * 24
        return int(max_count), int(cache_time)

    @wsexpose(models.PreChargeSimple)
    def used(self):
        conn = pecan.request.db_conn
        context = pecan.request.context
        user_id = context.user_id
        project_id = context.project_id
        user_name = context.user_name

        key = str("gring-precharge-limit-%s" % user_id)
        cache = _get_cache()
        count = cache.get(key)

        max_count, lock_time = \
            self._parse_limit_rule(cfg.CONF.precharge_limit_rule)

        if count is None:
            cache.set(key, str(max_count), lock_time)
            count = max_count

        price = utils._quantize_decimal('0')
        ret_code = 0

        if int(count) > 0:
            try:
                precharge = conn.use_precharge(context,
                                               self.code,
                                               user_id=user_id,
                                               project_id=project_id)
                price = precharge.price
            except exception.PreChargeNotFound:
                LOG.error('The precharge %s not found' % self.code)
                ret_code = 1
                try:
                    cache.decr(key)
                except AttributeError:
                    cache.incr(key, delta=-1)
            except exception.PreChargeHasUsed:
                LOG.error('The precharge %s has been used' % self.code)
                ret_code = 2
                try:
                    cache.decr(key)
                except AttributeError:
                    cache.incr(key, delta=-1)
            except exception.PreChargeHasExpired:
                LOG.error('The precharge %s has been expired' % self.code)
                ret_code = 3
                try:
                    cache.decr(key)
                except AttributeError:
                    cache.incr(key, delta=-1)
            except Exception as e:
                LOG.error('Fail to use precharge(%s), for reason: %s' %
                          (self.code, e))
                try:
                    cache.decr(key)
                except AttributeError:
                    cache.incr(key, delta=-1)
                raise exception.PreChargeException()
            else:
                cache.set(key, str(max_count), lock_time)
                # Notifier account
                if cfg.CONF.notify_account_charged:
                    account = conn.get_account(context, user_id).as_dict()
                    contact = keystone.get_uos_user(user_id)
                    self.notifier = notifier.NotifierService(
                        cfg.CONF.checker.notifier_level)
                    self.notifier.notify_account_charged(
                        context, account, contact,
                        'coupon', price, bonus=0,
                        operator=user_id,
                        operator_name=user_name,
                        remarks='coupon'
                    )
        left_count = int(cache.get(key))

        if left_count == 0:
            ret_code = 4

        return models.PreChargeSimple.transform(price=price,
                                                ret_code=ret_code,
                                                left_count=left_count,
                                                lock_time=lock_time / 60)


class PrechargesDispatchedController(rest.RestController):
    """Dispatch multiple precharges."""

    @wsexpose(None, body=models.PreChargesDispatchedBody, status_code=204)
    def put(self, data):
        conn = pecan.request.db_conn
        context = pecan.request.context
        check_policy(context, "account:precharge")

        if data.codes == wsme.Unset:
            data.codes = []
        if data.remarks == wsme.Unset:
            data.remarks = None

        for code in data.codes:
            if not code:
                continue
            try:
                conn.dispatch_precharge(context, code, data.remarks)
            except Exception as e:
                LOG.error('Fail to dispatch precharge(%s), for reason: %s' %
                          (self.code, e))


class PrechargesController(rest.RestController):
    """Manage operations on Precharges."""

    dispatched = PrechargesDispatchedController()

    @pecan.expose()
    def _lookup(self, code, *remainder):
        if remainder and not remainder[-1]:
            remainder = remainder[:-1]
        if len(code) == 16:
            return PrechargeController(code), remainder

    @wsexpose(None, body=models.PreChargeBody, status_code=201)
    def post(self, data):
        context = pecan.request.context
        check_policy(context, "account:precharge")

        conn = pecan.request.db_conn
        if data.expired_at == wsme.Unset:
            data.expired_at = datetime.datetime.utcnow() + \
                datetime.timedelta(days=365)
        if data.remarks == wsme.Unset:
            data.remarks = None

        try:
            conn.create_precharge(context, **data.as_dict())
        except exception.NotAuthorized as e:
            LOG.exception('Fail to create precharges')
            raise exception.NotAuthorized()
        except Exception as e:
            LOG.exception('Fail to create precharges: %s, for reason: %s' %
                          (data.as_dict(), e))
            raise exception.PreChargeException()

    @wsexpose(None)
    def put(self):
        context = pecan.request.context
        if not context.is_admin:
            raise exception.NotAuthorized()

        user_id = context.user_id
        key = str("gring-precharge-limit-%s" % user_id)
        cache = _get_cache()
        cache.delete(key)

    @wsexpose(models.PreCharges, wtypes.text, int, int,
              wtypes.text, wtypes.text)
    def get_all(self, user_id=None, limit=None, offset=None,
                sort_key='dispatched,used', sort_dir='asc'):
        """Get all precharges."""
        context = pecan.request.context
        conn = pecan.request.db_conn
        check_policy(context, "account:precharge")

        try:
            precharges = conn.get_precharges(context,
                                             user_id=user_id,
                                             limit=limit,
                                             offset=offset,
                                             sort_key=sort_key,
                                             sort_dir=sort_dir)
            total_count = conn.get_precharges_count(context, user_id=user_id)
            pecan.response.headers['X-Total-Count'] = str(total_count)
        except Exception as e:
            LOG.exception('Failed to get all precharges')
            raise exception.DBError(reason=e)

        precharges = [models.PreCharge.from_db_model(p) for p in precharges]
        return models.PreCharges.transform(precharges=precharges,
                                           total_count=total_count)

    @wsexpose(None, body=models.PreChargesCodeBody, status_code=204)
    def delete(self, data):
        conn = pecan.request.db_conn
        context = pecan.request.context
        check_policy(context, "account:precharge")

        if data.codes == wsme.Unset:
            data.codes = []
        for code in data.codes:
            if not code:
                continue
            try:
                conn.delete_precharge(context, code)
            except Exception as e:
                msg = 'Failed to delete precharge:%s, for reason:%s' % \
                    (code, e)
                LOG.exception(msg)
