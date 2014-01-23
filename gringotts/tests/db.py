# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
# Copyright © 2013 eNovance
#
# Author: Doug Hellmann <doug.hellmann@dreamhost.com>
#         Julien Danjou <julien@danjou.info>
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

"""Base classes for API tests."""
import os

from gringotts.openstack.common.fixture import config
from gringotts import db 
from gringotts.tests import base as test_base


class TestBase(test_base.BaseTestCase):
    def setUp(self):
        super(TestBase, self).setUp()
        self.CONF = self.useFixture(config.Config()).conf
        self.CONF.set_override('connection', str(self.database_connection),
                               group='database')
        self.conn = db.get_connection(self.CONF)
        self.conn.upgrade()

        self.CONF([], project='gringotts')
        )

    def tearDown(self):
        self.conn.clear()
        self.conn = None
        super(TestBase, self).tearDown()
