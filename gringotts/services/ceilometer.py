from oslo.config import cfg
from ceilometerclient import client as cmclient
from ceilometerclient.openstack.common.apiclient.exceptions import NotFound

from gringotts import utils
from gringotts import constants as const

from gringotts.openstack.common import log

from gringotts.openstack.common import timeutils
from gringotts.services import keystone as ks_client
from gringotts.services import wrap_exception
from gringotts.services import Resource


LOG = log.getLogger(__name__)


class Alarm(Resource):
    def to_message(self):
        msg = {
            'event_type': 'alarm.creation.again',
            'payload': {
                'alarm_id': self.id,
                'detail': {
                    'name': self.name,
                },
                'user_id': self.user_id,
                'project_id': self.project_id
            },
            'timestamp': utils.format_datetime(timeutils.strtime())
        }
        return msg

def get_cmclient(region_name=None):
    endpoint = ks_client.get_endpoint(region_name, 'metering')
    auth_token = ks_client.get_token()
    return cmclient.get_client(2,
                               os_auth_token=(lambda: auth_token),
                               ceilometer_url=endpoint)


@wrap_exception(exc_type='get')
def alarm_get(alarm_id, region_name=None):
    try:
        alarm = get_cmclient(region_name).alarms.get(alarm_id)
    except NotFound:
        return None

    # ceilometerclient will also return None if alarm doesn't exists
    if not alarm:
        return None

    status = utils.transform_status(str(alarm.enabled))
    return Alarm(id=alarm.alarm_id,
                 name=alarm.name,
                 status=status,
                 original_status=str(alarm.enabled),
                 resource_type=const.RESOURCE_ALARM)


@wrap_exception(exc_type='list')
def alarm_list(project_id, region_name=None, project_name=None):
    alarms = get_cmclient(region_name).alarms.list(q=[{'field': 'project_id',
                                                       'value': project_id}])
    formatted_alarms = []
    for alarm in alarms:
        created_at = utils.format_datetime(alarm.created_at)
        status = utils.transform_status(str(alarm.enabled))
        formatted_alarms.append(Alarm(id=alarm.alarm_id,
                                      name=alarm.name,
                                      status=status,
                                      original_status=str(alarm.enabled),
                                      resource_type=const.RESOURCE_ALARM,
                                      user_id=alarm.user_id,
                                      project_id=project_id,
                                      project_name=project_name,
                                      created_at=created_at))
    return formatted_alarms


@wrap_exception(exc_type='bulk')
def delete_alarms(project_id, region_name=None):
    client = get_cmclient(region_name)
    alarms = client.alarms.list(q=[{'field': 'enabled',
                                    'value': 'True'},
                                   {'field': 'project_id',
                                    'value': project_id}])
    for alarm in alarms:
        client.alarms.delete(alarm.alarm_id)
        LOG.warn("Delete alarm: %s" % alarm.alarm_id)


@wrap_exception(exc_type='delete')
def delete_alarm(alarm_id, region_name=None):
    get_cmclient(region_name).alarms.delete(alarm_id)


@wrap_exception(exc_type='stop')
def stop_alarm(alarm_id, region_name):
    return True
