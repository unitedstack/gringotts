import wsme
import pecan
import datetime

from pecan import rest
from wsmeext.pecan import wsexpose
from wsme import types as wtypes

from gringotts import exception
from gringotts import utils
from gringotts.api.v1 import models
from gringotts.openstack.common import timeutils
from gringotts.openstack.common import log


LOG = log.getLogger(__name__)


class PrechargeController(rest.RestController):
    """Manage operations on a single precharge
    """

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
        except Exception as e:
            LOG.error('Precharge(%s) not found' % self.code)
            raise exception.PreChargeNotFound(precharge_code=self.code)
        return precharge

    @wsexpose(models.PreCharge)
    def get(self):
        return models.PreCharge.from_db_model(self._precharge())

    @wsexpose(models.PreCharge, wtypes.text, body=models.PreChargeDispatched)
    def dispatched(self, data):
        conn = pecan.request.db_conn
        if data.remarks == wsme.Unset:
            data.remarks = None

        try:
            precharge = conn.dispatch_precharge(pecan.request.context,
                                                self.code,
                                                remarks=data.remarks)
        except exception.PreChargeNotFound:
            LOG.error('The precharge %s not found' % self.code)
            raise exception.PreChargeNotFound(precharge_code=self.code)
        except Exception as e:
            LOG.error('Fail to dispatch precharge(%s), for reason: %s' % (self.code, e))
            raise exception.PreChargeException()

        return models.PreCharge.from_db_model(precharge)

    @wsexpose(models.PreChargeSimple)
    def used(self):
        conn = pecan.request.db_conn
        user_id = pecan.request.context.user_id
        project_id = pecan.request.context.project_id

        price = utils._quantize_decimal('0')
        ret_code = 0

        try:
            precharge = conn.use_precharge(pecan.request.context,
                                           self.code,
                                           user_id=user_id,
                                           project_id=project_id)
            price = precharge.price
        except exception.PreChargeNotFound:
            LOG.error('The precharge %s not found' % self.code)
            ret_code = 1
        except exception.PreChargeHasUsed:
            LOG.error('The precharge %s has been used' % self.code)
            ret_code = 2
        except Exception as e:
            LOG.error('Fail to use precharge(%s), for reason: %s' % (self.code, e))
            raise exception.PreChargeException()

        return models.PreChargeSimple.transform(price=price,
                                                ret_code=ret_code)


class PrechargesController(rest.RestController):
    """Manage operations on Precharges
    """
    @pecan.expose()
    def _lookup(self, code, *remainder):
        if remainder and not remainder[-1]:
            remainder = remainder[:-1]
        return PrechargeController(code), remainder

    @wsexpose(None, body=models.PreChargeBody)
    def post(self, data):
        conn = pecan.request.db_conn
        if data.expired_at == wsme.Unset:
            data.expired_at = datetime.datetime.utcnow() + datetime.timedelta(days=365)

        try:
            conn.create_precharge(pecan.request.context, **data.as_dict())
        except exception.NotAuthorized as e:
            LOG.exception('Fail to create precharges')
            raise exception.NotAuthorized()
        except Exception as e:
            LOG.exception('Fail to create precharges: %s, for reason: %s' %
                          (data.as_dict(), e))
            raise exception.PreChargeException()

    @wsexpose([models.PreCharge], wtypes.text, int, int)
    def get_all(self, project_id=None, limit=None, offset=None):
        """Get all precharges
        """
        conn = pecan.request.db_conn
        precharges = conn.get_precharges(pecan.request.context,
                                         project_id=project_id,
                                         limit=limit,
                                         offset=offset)
        r = [models.PreCharge.from_db_model(p) for p in precharges]
        return r
