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
from tempest.lib import exceptions

from trove_tempest_plugin.tests import base as trove_base
from trove_tempest_plugin.tests import constants
from trove_tempest_plugin.tests import utils

LOG = logging.getLogger(__name__)


class TestInstanceBasicMySQLBase(trove_base.BaseTroveTest):
    def _access_db(self, ip, username=constants.DB_USER,
                   password=constants.DB_PASS, database=constants.DB_NAME):
        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306/{database}'
        LOG.info(f'Trying to access the database {db_url}')
        db_client = utils.SQLClient(db_url)

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

    @decorators.idempotent_id("c5a9dcda-af5b-11ea-b87c-00224d6b7bc1")
    def test_user_database(self):
        db1 = 'foo'
        db2 = 'bar'
        user1 = 'foo_user'
        user2 = 'bar_user'

        users = self.get_users(self.instance_id)
        cur_user_names = [user['name'] for user in users]
        self.assertNotIn(user1, cur_user_names)
        self.assertNotIn(user2, cur_user_names)

        databases = self.get_databases(self.instance_id)
        cur_db_names = [db['name'] for db in databases]
        self.assertNotIn(db1, cur_db_names)
        self.assertNotIn(db2, cur_db_names)

        LOG.info(f"Creating databases in instance {self.instance_id}")
        create_db = {
            "databases": [
                {
                    "name": db1
                },
                {
                    "name": db2
                }
            ]
        }
        self.client.create_resource(f"instances/{self.instance_id}/databases",
                                    create_db, expected_status_code=202,
                                    need_response=False)

        databases = self.get_databases(self.instance_id)
        cur_db_names = [db['name'] for db in databases]
        self.assertIn(db1, cur_db_names)
        self.assertIn(db2, cur_db_names)

        LOG.info(f"Creating users in instance {self.instance_id}")
        create_user = {
            "users": [
                {
                    "databases": [
                        {
                            "name": db1
                        }
                    ],
                    "name": user1,
                    "password": constants.DB_PASS
                },
                {
                    "name": user2,
                    "password": constants.DB_PASS
                }
            ]
        }
        self.client.create_resource(f"instances/{self.instance_id}/users",
                                    create_user, expected_status_code=202,
                                    need_response=False)

        users = self.get_users(self.instance_id)
        cur_user_names = [user['name'] for user in users]
        self.assertIn(user1, cur_user_names)
        self.assertIn(user2, cur_user_names)

        # user1 should have access to db1
        self._access_db(self.instance_ip, user1, constants.DB_PASS, db1)
        # user2 should not have access to db2
        self.assertRaises(exceptions.TempestException, self._access_db,
                          self.instance_ip, user2, constants.DB_PASS, db2)

        LOG.info(f"Granting user {user2} access to database {db2}")
        grant_access = {
            "databases": [
                {
                    "name": db2
                }
            ]
        }
        self.client.put_resource(
            f'/instances/{self.instance_id}/users/{user2}/databases',
            grant_access)
        user2_dbs = self.client.list_resources(
            f'instances/{self.instance_id}/users/{user2}/databases')
        user2_dbs = [db['name'] for db in user2_dbs['databases']]
        self.assertIn(db2, user2_dbs)
        # Now user2 should have access to db2
        self._access_db(self.instance_ip, user2, constants.DB_PASS, db2)

        LOG.info(f"Revoking user {user2} access to database {db2}")
        self.client.delete_resource(
            f'instances/{self.instance_id}/users/{user2}/databases', db2)
        # user2 should not have access to db2
        self.assertRaises(exceptions.TempestException, self._access_db,
                          self.instance_ip, user2, constants.DB_PASS, db2)

        LOG.info(f"Deleting user {user2}")
        self.client.delete_resource(
            f'instances/{self.instance_id}/users', user2)
        users = self.get_users(self.instance_id)
        cur_user_names = [user['name'] for user in users]
        self.assertIn(user1, cur_user_names)
        self.assertNotIn(user2, cur_user_names)

        LOG.info(f"Deleting database {db2}")
        self.client.delete_resource(
            f'instances/{self.instance_id}/databases', db2)
        databases = self.get_databases(self.instance_id)
        cur_db_names = [db['name'] for db in databases]
        self.assertIn(db1, cur_db_names)
        self.assertNotIn(db2, cur_db_names)
