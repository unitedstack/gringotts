import calendar
import pecan
import wsme
import datetime
import decimal

from pecan import rest
from pecan import request
from wsmeext.pecan import wsexpose
from wsme import types as wtypes

from oslo_config import cfg

from gringotts import exception
from gringotts import utils as gringutils

from gringotts.api import acl
from gringotts.api.v2 import models
from gringotts.db import models as db_models
from gringotts.openstack.common import log
from gringotts.openstack.common import timeutils
from gringotts.openstack.common import uuidutils


LOG = log.getLogger(__name__)


class SubsController(rest.RestController):
    """The controller of resources."""
    @wsexpose([models.Subscription], wtypes.text, wtypes.text, wtypes.text)
    def get_all(self, order_id=None, type=None, product_id=None):
        user_id = acl.get_limited_to_user(request.headers, 'subs:all')
        conn = pecan.request.db_conn
        subs = conn.get_subscriptions_by_order_id(request.context, order_id,
                                                  user_id=user_id,
                                                  type=type,
                                                  product_id=product_id)
        return [models.Subscription.from_db_model(s) for s in subs]

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
        if data.quantity != wtypes.Unset:
            conn.update_subscription(request.context,
                                     **data.as_dict())
        elif data.new_flavor != wtypes.Unset and data.old_flavor != wtypes.Unset:
            conn.update_flavor_subscription(request.context,
                                            **data.as_dict())
