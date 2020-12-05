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

from trove_tempest_plugin.tests.scenario import base_update_access as base


class TestInstanceUpdateAccessMySQL(base.TestInstanceUpdateAccessBase):
    datastore = 'mysql'


class TestInstanceUpdateAccessMariaDB(base.TestInstanceUpdateAccessBase):
    datastore = 'mariadb'


class TestInstanceUpdateAccessPostgreSQL(base.TestInstanceUpdateAccessBase):
    datastore = 'postgresql'
