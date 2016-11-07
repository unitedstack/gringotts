import pecan
import wsme

from pecan import rest
from pecan import request
from wsmeext.pecan import wsexpose
from wsme import types as wtypes

from oslo_db import exception as db_exc

from gringotts.policy import check_policy
from gringotts import exception
from gringotts import utils as gringutils
from gringotts.api.v2 import models
from gringotts.openstack.common import log


LOG = log.getLogger(__name__)


class GetBalanceController(rest.RestController):
    """Get balance of specified account."""
    @wsexpose(models.GetBalanceResponse, wtypes.text)
    def get(self, accountNum):

        check_policy(request.context, "deduct:account_get")
        self.conn = pecan.request.db_conn

        try:
            account = self.conn.get_account(request.context, accountNum)
        except Exception:
            LOG.error('account %s not found' % accountNum)
            raise exception.AccountNotFound(user_id=accountNum)

        return models.GetBalanceResponse(code="0",
                                         total="1",
                                         message="OK",
                                         data=[models.GetBalance(money=account.balance)])


class CheckReqController(rest.RestController):
    """Check if the deduction is successfull."""

    @wsexpose(models.CheckReqResponse, wtypes.text)
    def get(self, reqId):

        check_policy(request.context, "deduct:check_req")
        self.conn = pecan.request.db_conn

        status = "0"
        try:
            self.conn.get_deduct(request.context, reqId)
        except exception.DeductNotFound:
            LOG.warn('Deduct Req: %s not found' % reqId)
            status = "-1"
        except exception.NotAuthorized:
            LOG.exception('Fail to get the deduct req: %s' % reqId)
            raise exception.NotAuthorized()
        except Exception:
            msg = "Fail to get the deduct req: %s" % reqId
            LOG.exception(msg)
            raise exception.DBError(reason=msg)
        return models.CheckReqResponse(code="0",
                                       total="1",
                                       message="OK",
                                       data=[models.CheckReq(status=status)])


class PayController(rest.RestController):
    """Handle the deduct logic."""
    @wsexpose(models.PayResponse, body=models.PayRequest)
    def put(self, data):

        check_policy(request.context, "deduct:account_pay")

        if data.reqId == wsme.Unset or data.money == wsme.Unset or \
                data.accountNum == wsme.Unset or data.extData == wsme.Unset or \
                data.extData.order_id == wsme.Unset:
            raise exception.InvalidDeductParameter()

        data.money = gringutils._quantize_decimal(data.money)
        self.conn = pecan.request.db_conn

        try:
            deduct = self.conn.deduct_account(request.context,
                                              data.accountNum,
                                              **data.as_dict())
        except db_exc.DBDuplicateEntry:
            LOG.exception('Duplicated deduct req_id: %s' % data.reqId)
            raise exception.DuplicatedDeduct(req_id=data.reqId)
        except exception.NotAuthorized:
            LOG.exception('Fail to deduct the account: %s' % data.accountNum)
            raise exception.NotAuthorized()
        except Exception:
            msg = "Fail to deduct the account: %s, charge value: %s" % (data.accountNum, data.money)
            LOG.exception(msg)
            raise exception.DBError(reason=msg)

        pay = models.Pay(transactionNum=deduct.deduct_id,
                         money=deduct.money,
                         createDate=deduct.created_at)

        return models.PayResponse(code="0", total="1", message="OK", data=[pay])
