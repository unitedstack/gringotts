from oslo_config import cfg

from gringotts.openstack.common.rpc import proxy


cfg.CONF.import_opt('master_topic', 'gringotts.master.service',
                    group='master')


class MasterAPI(proxy.RpcProxy):
    BASE_RPC_VERSION = '1.0'

    def __init__(self):
        super(MasterAPI, self).__init__(
            topic=cfg.CONF.master.master_topic,
            default_version=self.BASE_RPC_VERSION)

    def create_monthly_job(self, ctxt, order_id, run_date):
        return self.cast(ctxt,
                         self.make_msg('create_monthly_job',
                                       order_id=order_id,
                                       run_date=run_date))

    def change_monthly_job_time(self, ctxt, order_id, run_date,
                                clear_date_jobs=None):
        return self.cast(ctxt,
                         self.make_msg('change_monthly_job_time',
                                       order_id=order_id,
                                       run_date=run_date,
                                       clear_date_jobs=clear_date_jobs))

    def delete_sched_jobs(self, ctxt, order_id):
        return self.cast(ctxt,
                         self.make_msg('delete_sched_jobs',
                                       order_id=order_id))

    def get_apsched_jobs_count(self, ctxt):
        return self.call(ctxt,
                         self.make_msg('get_apsched_jobs_count'))

    def resource_created(self, ctxt, order_id, action_time, remarks):
        return self.cast(ctxt,
                         self.make_msg('resource_created',
                                       order_id=order_id,
                                       action_time=action_time,
                                       remarks=remarks))

    def resource_created_again(self, ctxt, order_id, action_time, remarks):
        return self.cast(ctxt,
                         self.make_msg('resource_created_again',
                                       order_id=order_id,
                                       action_time=action_time,
                                       remarks=remarks))

    def resource_started(self, ctxt, order_id, action_time, remarks):
        return self.cast(ctxt,
                         self.make_msg('resource_started',
                                       order_id=order_id,
                                       action_time=action_time,
                                       remarks=remarks))

    def resource_stopped(self, ctxt, order_id, action_time, remarks):
        return self.cast(ctxt,
                         self.make_msg('resource_stopped',
                                       order_id=order_id,
                                       action_time=action_time,
                                       remarks=remarks))

    def resource_deleted(self, ctxt, order_id, action_time, remarks):
        return self.cast(ctxt,
                         self.make_msg('resource_deleted',
                                       order_id=order_id,
                                       action_time=action_time,
                                       remarks=remarks))

    def resource_changed(self, ctxt, order_id, action_time, change_to, remarks):
        return self.cast(ctxt,
                         self.make_msg('resource_changed',
                                       order_id=order_id,
                                       action_time=action_time,
                                       change_to=change_to,
                                       remarks=remarks))

    def resource_resized(self, ctxt, order_id, action_time, quantity, remarks):
        return self.call(ctxt,
                         self.make_msg('resource_resized',
                                       order_id=order_id,
                                       action_time=action_time,
                                       quantity=quantity,
                                       remarks=remarks))

    def instance_stopped(self, ctxt, order_id, action_time):
        return self.cast(ctxt,
                         self.make_msg('instance_stopped',
                                       order_id=order_id,
                                       action_time=action_time))

    def instance_resized(self, ctxt, order_id, action_time,
                         new_flavor, old_flavor,
                         service, region_id, remarks):
        return self.cast(ctxt,
                         self.make_msg('instance_resized',
                                       order_id=order_id,
                                       action_time=action_time,
                                       new_flavor=new_flavor,
                                       old_flavor=old_flavor,
                                       service=service,
                                       region_id=region_id,
                                       remarks=remarks))
