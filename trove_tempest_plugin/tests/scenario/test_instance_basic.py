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
from oslo_service import loopingcall
from tempest.lib import decorators
from tempest.lib import exceptions

from trove_tempest_plugin.tests import constants
from trove_tempest_plugin.tests.scenario import base_basic
from trove_tempest_plugin.tests import utils


LOG = logging.getLogger(__name__)


class TestInstanceBasicMySQL(base_basic.TestInstanceBasicMySQLBase):
    datastore = 'mysql'


class TestInstanceBasicMariaDB(base_basic.TestInstanceBasicMySQLBase):
    datastore = 'mariadb'


class TestInstanceBasicPostgreSQL(base_basic.TestInstanceBasicBase):
    datastore = 'postgresql'
    create_user = True
    enable_root = True

    def _access_db(self, ip, username=constants.DB_USER,
                   password=constants.DB_PASS, database=constants.DB_NAME):
        db_url = f'postgresql+psycopg2://{username}:{password}@{ip}:5432/'\
            f'{database}'
        with utils.SQLClient(db_url) as db_client:
            cmd = "SELECT 1;"
            db_client.pgsql_execute(cmd)

    def get_config_value(self, ip, option):
        db_url = (f'postgresql+psycopg2://root:{self.password}@'
                  f'{ip}:5432/postgres')
        with utils.SQLClient(db_url) as db_client:
            cmd = f"SELECT setting FROM pg_settings WHERE name='{option}';"
            ret = db_client.pgsql_execute(cmd)
            rows = ret.fetchall()

        self.assertEqual(1, len(rows))
        return int(rows[0][0])

    @decorators.idempotent_id('e9f78628-8bf9-46fb-84b2-367de3f0e0fe')
    def test_database_access(self):
        databases = self.get_databases(self.instance_id)
        db_names = [db['name'] for db in databases]
        self.assertIn(constants.DB_NAME, db_names)

        users = self.get_users(self.instance_id)
        user_names = [user['name'] for user in users]
        self.assertIn(constants.DB_USER, user_names)

        LOG.info(f"Accessing database on {self.instance_ip}")
        self._access_db(self.instance_ip)

    @decorators.idempotent_id('6c2c710c-0138-4215-8e08-6dfe605ba6a6')
    def test_user_database(self):
        db1 = 'foo'
        user1 = 'foo_user'
        user2 = 'bar_user'

        users = self.get_users(self.instance_id)
        cur_user_names = [user['name'] for user in users]
        self.assertNotIn(user1, cur_user_names)

        databases = self.get_databases(self.instance_id)
        cur_db_names = [db['name'] for db in databases]
        self.assertNotIn(db1, cur_db_names)

        LOG.info(f"Creating databases in instance {self.instance_id}")
        create_db = {
            "databases": [
                {
                    "name": db1
                }
            ]
        }
        self.client.create_resource(f"instances/{self.instance_id}/databases",
                                    create_db, expected_status_code=202,
                                    need_response=False)

        def _wait_db():
            try:
                databases = self.get_databases(self.instance_id)
                cur_db_names = [db['name'] for db in databases]
                self.assertIn(db1, cur_db_names)
                raise loopingcall.LoopingCallDone()
            except AssertionError:
                return
        timer = loopingcall.FixedIntervalWithTimeoutLoopingCall(_wait_db)
        try:
            timer.start(interval=5, timeout=30, initial_delay=5).wait()
        except loopingcall.LoopingCallTimeOut as e:
            message = f"failed to create db: {db1} in 30 seconds"
            raise exceptions.TimeoutException(message) from e

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
                }
            ]
        }
        self.client.create_resource(f"instances/{self.instance_id}/users",
                                    create_user, expected_status_code=202,
                                    need_response=False)
        time.sleep(3)
        users = self.get_users(self.instance_id)
        cur_user_names = [user['name'] for user in users]
        self.assertIn(user1, cur_user_names)

        # user1 should have access to db1
        LOG.info(f"Accessing database on {self.instance_ip}, user: {user1}, "
                 f"db: {db1}")
        self._access_db(self.instance_ip, user1, constants.DB_PASS, db1)

        LOG.info(f"Revoking user {user1} access to database {db1}")
        self.client.delete_resource(
            f'instances/{self.instance_id}/users/{user1}/databases', db1)
        # FIXME: user1 still have access to db1 because of the
        # havior of public schema
        # self.assertRaises(exceptions.TempestException, self._access_db,
        #                   self.instance_ip, user1, constants.DB_PASS, db1)
        # self.assertFalse(self._check_db_privilege(self.instance_ip,
        #                                          user1,
        #                                          constants.DB_PASS, db1))

        # test update_attributes interface
        LOG.info(f"Updating user {user1} to {user2}")
        new_user_body = {"user": {"name": user2}}
        self.client.put_resource(
            f'instances/{self.instance_id}/users/{user1}', new_user_body)
        time.sleep(3)
        users = self.get_users(self.instance_id)
        cur_user_names = [user['name'] for user in users]
        self.assertIn(user2, cur_user_names)

        LOG.info(f"Deleting user {user2}")
        self.client.delete_resource(
            f'instances/{self.instance_id}/users', user2)
        time.sleep(3)
        users = self.get_users(self.instance_id)
        cur_user_names = [user['name'] for user in users]
        self.assertNotIn(user2, cur_user_names)

        LOG.info(f"Deleting database {db1}")
        self.client.delete_resource(
            f'instances/{self.instance_id}/databases', db1)
        # Wait for database deletion to complete
        self.wait_for_database_deletion(self.instance_id, db1)
        databases = self.get_databases(self.instance_id)
        cur_db_names = [db['name'] for db in databases]
        self.assertNotIn(db1, cur_db_names)

    @decorators.idempotent_id("b6c03cb6-f40f-11ea-a950-00224d6b7bc1")
    def test_configuration(self):
        # Default is 100
        create_values = {"max_connections": 101}
        update_values = {"max_connections": 102}
        self.configuration_test(create_values, update_values,
                                need_restart=True)
