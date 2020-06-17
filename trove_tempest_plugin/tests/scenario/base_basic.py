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
from tempest import config
from tempest.lib import decorators
from tempest.lib import exceptions

from trove_tempest_plugin.tests import base as trove_base
from trove_tempest_plugin.tests import constants
from trove_tempest_plugin.tests import utils

CONF = config.CONF
LOG = logging.getLogger(__name__)


class TestInstanceBasicMySQLBase(trove_base.BaseTroveTest):
    def _access_db(self, ip, username=constants.DB_USER,
                   password=constants.DB_PASS, database=constants.DB_NAME):
        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306/{database}'
        LOG.info(f'Trying to access the database {db_url}')
        db_client = utils.SQLClient(db_url)

        cmd = "SELECT 1;"
        db_client.execute(cmd)

    def get_config_value(self, ip, option, username=constants.DB_USER,
                         password=constants.DB_PASS):
        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306'
        LOG.info(f'Trying to get option value for {option} from database '
                 f'{db_url}')
        db_client = utils.SQLClient(db_url)

        cmd = f"show variables where Variable_name in ('{option}');"
        ret = db_client.execute(cmd)
        rows = ret.fetchall()
        self.assertEqual(1, len(rows))
        return rows[0][1]

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

    @decorators.idempotent_id("ce8277b0-af7c-11ea-b87c-00224d6b7bc1")
    def test_configuration(self):
        # Create new configuration
        config_name = 'test_config'
        new_value = 555
        create_config = {
            "configuration": {
                "datastore": {
                    "type": self.datastore,
                    "version": self.instance['datastore']['version']
                },
                "values": {
                    "max_connections": new_value
                },
                "name": config_name
            }
        }
        LOG.info(f"Creating new configuration {config_name}")
        config = self.client.create_resource('configurations', create_config)
        config_id = config['configuration']['id']
        self.addCleanup(self.client.delete_resource, 'configurations',
                        config_id, ignore_notfound=True)
        self.assertEqual(0, config['configuration']['instance_count'])

        ret = self.client.list_resources(
            f"configurations/{config_id}/instances")
        self.assertEqual(0, len(ret['instances']))

        # Attach the configuration to the existing instance
        attach_config = {
            "instance": {
                "configuration": config_id
            }
        }
        LOG.info(f"Attaching config {config_id} to instance "
                 f"{self.instance_id}")
        self.client.put_resource(f'instances/{self.instance_id}',
                                 attach_config)

        ret = self.client.list_resources(
            f"configurations/{config_id}/instances")
        self.assertEqual(1, len(ret['instances']))
        self.assertEqual(self.instance_id, ret['instances'][0]['id'])

        # Get new config option value
        cur_value = self._get_config_value(self.instance_ip, 'max_connections')
        self.assertEqual(new_value, int(cur_value))

        # Update configuration
        updated_value = 666
        patch_config = {
            "configuration": {
                "values": {
                    "max_connections": updated_value
                }
            }
        }
        LOG.info(f"Updating config {config_id}")
        self.client.patch_resource('configurations', config_id, patch_config,
                                   expected_status_code=200)

        cur_value = self._get_config_value(self.instance_ip, 'max_connections')
        self.assertEqual(updated_value, int(cur_value))

        # Detach the configuration from the instance
        detach_config = {
            "instance": {
                "configuration": ""
            }
        }
        self.client.put_resource(f'instances/{self.instance_id}',
                                 detach_config)

        ret = self.client.list_resources(
            f"configurations/{config_id}/instances")
        self.assertEqual(0, len(ret['instances']))

        # Get new config option value
        cur_value = self._get_config_value(self.instance_ip, 'max_connections')
        self.assertNotEqual(new_value, int(cur_value))
        self.assertNotEqual(updated_value, int(cur_value))
