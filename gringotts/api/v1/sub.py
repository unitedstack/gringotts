import calendar
import pecan
import wsme
import datetime
import decimal

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
from gringotts.openstack.common import timeutils
from gringotts.openstack.common import uuidutils


LOG = log.getLogger(__name__)


class SubsController(rest.RestController):
    """The controller of resources
    """
    @wsexpose(models.Subscription, body=models.SubscriptionPostBody)
    def post(self, data):
        conn = pecan.request.db_conn
        subscription = conn.create_subscription(request.context,
                                                **data.as_dict())
        if subscription:
            return models.Subscription.from_db_model(subscription)
        else:
            return None

    @wsexpose(None, body=models.SubscriptionPutBody)
    def put(self, data):
        conn = pecan.request.db_conn
        conn.update_subscription(request.context,
                                 **data.as_dict())
