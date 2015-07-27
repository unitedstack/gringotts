
import mock
from oslo_config import cfg
from oslotest import mockpatch

from gringotts.openstack.common import log as logging
from gringotts.tests import service as test_service
from gringotts.waiter.plugins import alarm
from gringotts.waiter.plugins import floatingip
from gringotts.waiter.plugins import image
from gringotts.waiter.plugins import instance
from gringotts.waiter.plugins import listener
from gringotts.waiter.plugins import router
from gringotts.waiter.plugins import share
from gringotts.waiter.plugins import snapshot
from gringotts.waiter.plugins import user as identity
from gringotts.waiter.plugins import volume

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class NotificationTestCase(test_service.WaiterServiceTestCase):

    def setUp(self):
        super(NotificationTestCase, self).setUp()

        self.useFixture(mockpatch.PatchObject(
            self.service, '_setup_subscription'))
        self.service.initialize_service_hook(self.service)

    def _test_notification_process(self, _class, event_type, result=True):
        message = self.build_notification_message(
            self.admin_account.user_id, event_type, {})
        with mock.patch.object(_class, 'process_notification') as handle:
            self.service.process_notification(message)
            self.assertEqual(result, handle.called)

    def test_alarm_create_end(self):
        self._test_notification_process(
            alarm.AlarmCreateEnd, 'alarm.creation')

    def test_alarm_on_off_end(self):
        self._test_notification_process(
            alarm.AlarmOnOffEnd, 'alarm.on/off')

    def test_alarm_delete_end(self):
        self._test_notification_process(
            alarm.AlarmDeleteEnd, 'alarm.deletion')

    def test_floatingip_create_end(self):
        self._test_notification_process(
            floatingip.FloatingIpCreateEnd, 'floatingip.create.end')

    def test_floatingip_resize_end(self):
        self._test_notification_process(floatingip.FloatingIpResizeEnd,
                                        'floatingip.update_ratelimit.end')

    def test_floatingip_delete_end(self):
        self._test_notification_process(
            floatingip.FloatingIpDeleteEnd, 'floatingip.delete.end')

    def test_floatingipset_create_end(self):
        self._test_notification_process(
            floatingip.FloatingIpCreateEnd, 'floatingipset.create.end')

    def test_floatingipset_resize_end(self):
        self._test_notification_process(
            floatingip.FloatingIpResizeEnd,
            'floatingipset.update_ratelimit.end')

    def test_floatingipset_delete_end(self):
        self._test_notification_process(
            floatingip.FloatingIpDeleteEnd, 'floatingipset.delete.end')

    def test_identity_user_register(self):
        self._test_notification_process(
            identity.UserRegisterEnd, 'identity.account.register')

    def test_identity_user_create_end(self):
        self._test_notification_process(
            identity.UserCreatedEnd, 'identity.user.create')

    def test_identity_project_create_end(self):
        self._test_notification_process(
            identity.ProjectCreatedEnd, 'identity.project.create')

    def test_identity_project_delete_end(self):
        self._test_notification_process(
            identity.ProjectDeletedEnd, 'identity.project.delete')

    def test_identity_billing_owner_changed_end(self):
        self._test_notification_process(
            identity.BillingOwnerChangedEnd, 'identity.billing_owner.changed')

    def test_image_create_end(self):
        self._test_notification_process(
            image.ImageCreateEnd, 'image.activate')

    def test_image_delete_end(self):
        self._test_notification_process(
            image.ImageDeleteEnd, 'image.delete')

    def test_instance_create_end(self):
        self._test_notification_process(
            instance.InstanceCreateEnd, 'compute.instance.create.end')

    def test_instance_stop_end_power_off(self):
        self._test_notification_process(
            instance.InstanceStopEnd, 'compute.instance.power_off.end')

    def test_instance_stop_end_shutdown2(self):
        self._test_notification_process(
            instance.InstanceStopEnd, 'compute.instance.shutdown2.end')

    def test_instance_start_end_power_on(self):
        self._test_notification_process(
            instance.InstanceStartEnd, 'compute.instance.power_on.end')

    def test_instance_start_end_reboot(self):
        self._test_notification_process(
            instance.InstanceStartEnd, 'compute.instance.reboot.end')

    def test_instance_resize_end(self):
        self._test_notification_process(
            instance.InstanceResizeEnd, 'compute.instance.local_resize.end')

    def test_instance_delete_end(self):
        self._test_notification_process(
            instance.InstanceDeleteEnd, 'compute.instance.delete.end')

    def test_instance_suspend_end(self):
        self._test_notification_process(
            instance.InstanceSuspendEnd, 'compute.instance.suspend')

    def test_instance_resume_end(self):
        self._test_notification_process(
            instance.InstanceResumeEnd, 'compute.instance.resume')

    def test_listener_create_end(self):
        self._test_notification_process(
            listener.ListenerCreateEnd, 'listener.create.end')

    def test_listener_update_end(self):
        self._test_notification_process(
            listener.ListenerUpdateEnd, 'listener.update.end')

    def test_listener_delete_end(self):
        self._test_notification_process(
            listener.ListenerDeleteEnd, 'listener.delete.end')

    def test_listener_load_balancer_delete_end(self):
        self._test_notification_process(
            listener.LoadBalancerDeleteEnd, 'loadbalancer.delete.end')

    def test_router_create_end(self):
        self._test_notification_process(
            router.RouterCreateEnd, 'router.create.end')

    def test_router_delete_end(self):
        self._test_notification_process(
            router.RouterDeleteEnd, 'router.delete.end')

    def test_share_create_end(self):
        self._test_notification_process(
            share.ShareCreateEnd, 'share.create.end')

    def test_share_delete_end(self):
        self._test_notification_process(
            share.ShareDeleteEnd, 'share.delete.end')

    def test_snapshot_create_end(self):
        self._test_notification_process(
            snapshot.SnapshotCreateEnd, 'snapshot.create.end')

    def test_snapshot_delete_end(self):
        self._test_notification_process(
            snapshot.SnapshotDeleteEnd, 'snapshot.delete.end')

    def test_volume_create_end(self):
        self._test_notification_process(
            volume.VolumeCreateEnd, 'volume.create.end')

    def test_volume_resize_end(self):
        self._test_notification_process(
            volume.VolumeResizeEnd, 'volume.resize.end')

    def test_volume_delete_end(self):
        self._test_notification_process(
            volume.VolumeDeleteEnd, 'volume.delete.end')
