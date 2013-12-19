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


class ProductItem(plugin.PluginBase):

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def get_product_filter(self, message):
        """Get product from message
        """

    @abc.abstractmethod
    def make_subscription_model(self, product_id, message):
        """Make subscription DB model
        """

    def get_product(self, context, message):
        filters = self.get_product_filter(message)
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
