# Copyright 2015 UnitedStack Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import copy
import sys

from keystoneclient import access
from gringotts.services import keystone as ks_client
from troveclient.v1 import client as trove_client
from oslo.config import cfg
import json

from gringotts.openstack.common.gettextutils import _
from gringotts.openstack.common import log as logging
from gringotts.services import wrap_exception


LOG = logging.getLogger(__name__)


def troveclient(project_id, region_name=None):
    os_cfg = cfg.CONF.service_credentials
    endpoint = ks_client.get_endpoint(region_name, 'database')
    auth_token = ks_client.get_token()

    tc = trove_client.Client(os_cfg.os_username,
                             os_cfg.os_password,
                             project_id=project_id,
                             auth_url=os_cfg.os_auth_url)

    tc.client.auth_token = auth_token
    tc.client.management_url = endpoint
    return tc

@wrap_exception(exc_type='get', with_raise=False)
def quota_get(project_id, region_name=None):
    client = troveclient(project_id, region_name)
    return client.mgmt_quota.show(project_id)


@wrap_exception(exc_type='put', with_raise=False)
def quota_update(project_id, region_name=None, **kwargs):
    troveclient(project_id, region_name).mgmt_quota.update(project_id, json.dumps(kwargs))
