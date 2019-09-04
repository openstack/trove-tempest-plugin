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
from tempest.lib import decorators

from trove_tempest_plugin.tests import base


class TestInstanceBasic(base.BaseTroveTest):
    @classmethod
    def resource_setup(cls):
        super(TestInstanceBasic, cls).resource_setup()

        cls.instance_id = cls.create_instance()
        cls.wait_for_instance_status(cls.instance_id)

    @decorators.idempotent_id("40cf38ce-cfbf-11e9-8760-1458d058cfb2")
    def test_database_access(self):
        pass
