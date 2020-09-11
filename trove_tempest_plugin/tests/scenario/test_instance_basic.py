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
from oslo_log import log as logging
from tempest.lib import decorators

from trove_tempest_plugin.tests.scenario import base_basic
from trove_tempest_plugin.tests import utils

LOG = logging.getLogger(__name__)


class TestInstanceBasicMySQL(base_basic.TestInstanceBasicMySQLBase):
    datastore = 'mysql'


class TestInstanceBasicMariaDB(base_basic.TestInstanceBasicMySQLBase):
    datastore = 'mariadb'


class TestInstanceBasicPostgreSQL(base_basic.TestInstanceBasicBase):
    datastore = 'postgresql'
    create_user = False
    enable_root = True

    def get_config_value(self, ip, option):
        db_url = (f'postgresql+psycopg2://root:{self.password}@'
                  f'{ip}:5432/postgres')
        with utils.SQLClient(db_url) as db_client:
            cmd = f"SELECT setting FROM pg_settings WHERE name='{option}';"
            ret = db_client.pgsql_execute(cmd)
            rows = ret.fetchall()

        self.assertEqual(1, len(rows))
        return int(rows[0][0])

    @decorators.idempotent_id("b6c03cb6-f40f-11ea-a950-00224d6b7bc1")
    def test_configuration(self):
        # Default is 100
        create_values = {"max_connections": 101}
        update_values = {"max_connections": 102}
        self.configuration_test(create_values, update_values,
                                need_restart=True)
