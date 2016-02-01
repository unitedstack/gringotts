from oslo_config import cfg
from stevedore import extension

from gringotts.openstack.common import log
from gringotts.openstack.common.rpc import service as rpc_service
from gringotts.openstack.common import service as os_service

from gringotts.service import prepare_service


LOG = log.getLogger(__name__)

OPTS = [
    cfg.BoolOpt('ack_on_event_error',
                default=True,
                help='Acknowledge message when event persistence fails'),
    cfg.StrOpt('queue_name',
               default='gringotts.notification',
               help='The queue to listen on exchange for waiter'),
    cfg.StrOpt('initial_balance',
               default='10',
               help='initial balance when an user registered'),
    cfg.IntOpt('initial_level',
               default=3,
               help='The limit that a account can deduct'),
    cfg.StrOpt('user_initial_balance',
               default='0',
               help='initial balance when an user be created'),
    cfg.IntOpt('user_initial_level',
               default=3,
               help='The limit that a user can deduct')

]

OPTS_GLOBAL = [
    cfg.StrOpt('region_name',
               default='RegionOne',
               help='The region this waiter is deployed'),
    cfg.StrOpt('cloud_name',
               default="localhost",
               help="The environment this service is running"),
    cfg.ListOpt('notification_email_receivers', default=[],
                help='Receivers of notification email.'),
]

cfg.CONF.register_opts(OPTS, group="waiter")
cfg.CONF.register_opts(OPTS_GLOBAL)


class WaiterService(rpc_service.Service):

    NOTIFICATION_NAMESPACE = 'gringotts.notification'

    def start(self):
        super(WaiterService, self).start()
        LOG.warn("Waiter Loaded Successfully")
        # Add a dummy thread to have wait() working
        self.tg.add_timer(604800, lambda: None)

    def initialize_service_hook(self, service):
        """Consumers must be declared before consume_thread start."""

        self.notification_manager = \
            extension.ExtensionManager(
                namespace=self.NOTIFICATION_NAMESPACE,
                invoke_on_load=True,
            )

        if not list(self.notification_manager):
            LOG.warning('Failed to load any notification handlers for %s',
                        self.NOTIFICATION_NAMESPACE)
        self.notification_manager.map(self._setup_subscription)

    def _setup_subscription(self, ext, *args, **kwds):
        """Connect to message bus to get notifications

        Configure the RPC connection to listen for messages on the
        right exchanges and topics so we receive all of the
        notifications.

        Use a connection pool so that multiple waiter instances can run
        in parallel to share load and without competing with each other
        for incoming messages.

        """
        handler = ext.obj
        ack_on_error = cfg.CONF.waiter.ack_on_event_error
        LOG.debug('Event types from %s: %s (ack_on_error=%s)',
                  ext.name, ', '.join(handler.event_types),
                  ack_on_error)

        for exchange_topic in handler.get_exchange_topics(cfg.CONF):
            for topic in exchange_topic.topics:
                try:
                    self.conn.join_consumer_pool(
                        callback=self.process_notification,
                        pool_name=cfg.CONF.waiter.queue_name,
                        topic=topic,
                        exchange_name=exchange_topic.exchange,
                        ack_on_error=ack_on_error)
                except Exception:
                    LOG.exception('Could not join consumer pool %s/%s' %
                                  (topic, exchange_topic.exchange))

    def process_notification(self, notification):
        """RPC endpoint for notification messages

        When another service sends a notification over the message
        bus, this method receives it. See _setup_subscription().

        """
        self.notification_manager.map(self._process_notification_for_ext,
                                      notification=notification)

    def _process_notification_for_ext(self, ext, notification):
        """Wrapper for doing actions  when a notification arrives

        When a message is received by process_notification(), it calls
        this method with each notification plugin to allow all the
        plugins process the notification.

        """
        # FIXME(suo): Spawn green thread?
        try:
            ext.obj.do_actions(notification)
        except Exception:
            LOG.exception("Some errors occured when handling event_type: %s,"
                          "the message content is: %s",
                          notification.get('event_type'),
                          notification)


def waiter():
    prepare_service()
    os_service.launch(WaiterService(cfg.CONF.host,
                                    'gringotts.waiter')).wait()
