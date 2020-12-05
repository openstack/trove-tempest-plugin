# Copyright 2020 Catalyst Cloud
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

from oslo_log import log as logging
from tempest.lib import decorators

from trove_tempest_plugin.tests import base as trove_base

LOG = logging.getLogger(__name__)


class TestInstanceUpdateAccessBase(trove_base.BaseTroveTest):
    """Update instance access base class.

    Updating instance access needs to change the public IP address of the
    instance, so we need a separate test class for this.
    """
    def update_access_test(self):
        """Test update instance accessbility"""
        if 'access' not in self.instance:
            raise self.skipException("Access not supported in API.")

        # Change instance to be private
        LOG.info(f"Changing instance {self.instance_id} to be private")
        body = {
            "instance": {
                "access": {
                    "is_public": False,
                }
            }
        }
        self.client.put_resource(f'instances/{self.instance_id}', body)
        self.wait_for_instance_status(self.instance_id, timeout=30)

        instance = self.client.get_resource(
            "instances", self.instance_id)['instance']
        self.assertFalse(instance['access']['is_public'])
        types = [addr['type'] for addr in instance['addresses']]
        self.assertNotIn('public', types)

        # Change back to public
        LOG.info(f"Changing instance {self.instance_id} to be public")
        body = {
            "instance": {
                "access": {
                    "is_public": True,
                }
            }
        }
        self.client.put_resource(f'instances/{self.instance_id}', body)
        self.wait_for_instance_status(self.instance_id, timeout=30)

    @decorators.idempotent_id("c907cc80-36b4-11eb-b177-00224d6b7bc1")
    def test_instance_update_access(self):
        self.update_access_test()
