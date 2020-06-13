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

from trove_tempest_plugin.tests import base as trove_base
from trove_tempest_plugin.tests import constants
from trove_tempest_plugin.tests import utils

LOG = logging.getLogger(__name__)


class TestInstanceBasicMySQLBase(trove_base.BaseTroveTest):
    def _access_db(self, ip, username=constants.DB_USER,
                   password=constants.DB_PASS):
        LOG.info('Trying to access the database %s', ip)

        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306'
        db_engine = utils.init_engine(db_url)
        db_client = utils.SQLClient(db_engine)

        cmd = "SELECT 1;"
        db_client.execute(cmd)

    @decorators.idempotent_id("40cf38ce-cfbf-11e9-8760-1458d058cfb2")
    def test_database_access(self):
        databases = self.get_databases(self.instance_id)
        db_names = [db['name'] for db in databases]
        self.assertIn(constants.DB_NAME, db_names)

        users = self.get_users(self.instance_id)
        user_names = [user['name'] for user in users]
        self.assertIn(constants.DB_USER, user_names)

        self._access_db(self.instance_ip)
