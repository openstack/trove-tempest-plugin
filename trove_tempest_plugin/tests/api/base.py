# Copyright 2019 Catalyst Cloud Ltd.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
import time

from oslo_log import log as logging
from tempest.lib import decorators

from trove_tempest_plugin.tests import base as trove_base

LOG = logging.getLogger(__name__)


class TestInstanceActionsBase(trove_base.BaseTroveTest):
    @decorators.idempotent_id("be6dd514-27d6-11ea-a56a-98f2b3cc23a0")
    def test_instance_upgrade(self):
        res = self.client.get_resource("instances", self.instance_id)
        datastore = res["instance"]['datastore']['type']
        version = res["instance"]['datastore']['version']
        new_version = version
        datastore = self.client.get_resource("datastores", datastore)
        for v in datastore['datastore']['versions']:
            if v['name'] != version:
                new_version = v['name']
                break

        LOG.info('Using datastore %s for instance upgrading', new_version)

        body = {
            "instance": {
                "datastore_version": new_version
            }
        }
        self.client.patch_resource('instances', self.instance_id, body)

        time.sleep(3)
        self.wait_for_instance_status(self.instance_id,
                                      expected_status="ACTIVE")
