import copy

from oslo.config import cfg

from gringotts import exception
from gringotts import db
from gringotts import plugin

db_conn = db.get_connection(cfg.CONF)

LOG = log.getLogger(__name__)


class ComputeNotificationBase(plugin.NotificationBase):
    @staticmethod
    def get_exchange_topics(conf):
        """Return a sequence of ExchangeTopics defining the exchange and
        topics to be connected for this plugin.
        """
        return [
            plugin.ExchangeTopics(
                exchange=conf.nova_control_exchange,
                topics=set(topic + ".info"
                           for topic in conf.notification_topics)),
        ]


class Collection(object):
    """Some field collection that ProductItem will use to get product or
    to create/update/delete subscription
    """
    def __init__(self, product_name, service, region_id, resource_id,
                 resource_name, resource_type, resource_status,
                 user_id, project_id, action_time):
        self.product_name = product_name
        self.service = service
        self.region_id = region_id
        self.resource_id = resource_id
        self.resource_name = resource_name
        self.resource_type = resource_type
        self.resource_status = resource_status
        self.user_id = user_id
        self.project_id = project_id
        self.action_time = action_time

    def as_dict():
        return copy.copy(self.__dict__)


class ProductItem(plugin.PluginBase):

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def get_collection(self, message):
        """Get collection from message
        """

    def _get_product(self, collection):
        """Get product from db
        """
        filters = dict(product_name=collection.product_name,
                       service=collection.collection,
                       region_id=collection.region_id)

        result = list(db_conn.get_products(None, filters=filters))

        if len(result) > 1:
            error = "Duplicated products with name(%s) within service(%s) in region_id(%s)" % \
                    (product_name, service, region_id)
            LOG.error(error)
            raise exception.DuplicatedProduct(reason=error)

        if len(result) == 0:
            error = "Product with name(%s) within service(%s) in region_id(%s) not found" % \
                    (product_name, service, region_id)
            LOG.warning(error)
            return None

        return result[0]

    def create_subscription(self):
        """Subscribe to this product"""
        collection = self.get_collection(message)
        product = self._get_product(collection)

        # Create subscription
        subscription_id = uuidutils.generate_uuid()
        resource_id = collection.resource_id
        resource_name = collection.resource_name
        resource_type = collection.resource_type
        resource_status = collection.resource_status
        product_id = product.product_id
        current_fee = 0
        cron_time = None
        status = 'active'
        user_id = collection.user_id
        project_id = collection.project_id

        subscription = db_models.Subscription(
                subscription_id, resource_id,
                resource_name, resource_type, resource_status, product_id,
                current_fee, cron_time, status, user_id, project_id)

        try:
            db_conn.create_subscription(None, subscription)
        except Exception:
            LOG.exception('Fail to create subscription: %s' % \
                          subscription.as_dict())
            raise exception.DBError(reason='Fail to create subscription')
        return subscription, product


    def get_subscription():
        pass
    
    def update_subscription():
        pass

    def delete_subscription():
        pass
