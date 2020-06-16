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

    def insert_data_replication(self, ip, username, password, database):
        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306/{database}'
        LOG.info(f"Inserting data for replication, db_url: {db_url}")
        db_client = utils.SQLClient(db_url)

        cmds = [
            "CREATE TABLE Persons (ID int, String varchar(255));",
            "insert into Persons VALUES (1, 'replication');"
        ]
        db_client.execute(cmds)

    def verify_data_replication(self, ip, username, password, database):
        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306/{database}'
        LOG.info(f"Verifying data for replication, db_url: {db_url}")
        db_client = utils.SQLClient(db_url)
        cmd = "select * from Persons;"
        ret = db_client.execute(cmd)
        keys = ret.keys()
        rows = ret.fetchall()
        self.assertEqual(1, len(rows))

        result = []
        for index in range(len(rows)):
            result.append(dict(zip(keys, rows[index])))
        expected = {'ID': 1, 'String': 'replication'}
        self.assert_single_item(result, **expected)

    def insert_data_after_promote(self, ip, username, password, database):
        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306/{database}'
        LOG.info(f"Inserting data after promotion, db_url: {db_url}")
        db_client = utils.SQLClient(db_url)

        cmds = [
            "insert into Persons VALUES (2, 'promote');"
        ]
        db_client.execute(cmds)

    def verify_data_after_promote(self, ip, username, password, database):
        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306/{database}'
        LOG.info(f"Verifying data after promotion, db_url: {db_url}")
        db_client = utils.SQLClient(db_url)
        cmd = "select * from Persons;"
        ret = db_client.execute(cmd)
        keys = ret.keys()
        rows = ret.fetchall()
        self.assertGreater(len(rows), 1)

        result = []
        for index in range(len(rows)):
            result.append(dict(zip(keys, rows[index])))
        expected = {'ID': 2, 'String': 'promote'}
        self.assert_single_item(result, **expected)

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
        cur_value = self.get_config_value(self.instance_ip, 'max_connections')
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

        cur_value = self.get_config_value(self.instance_ip, 'max_connections')
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
        cur_value = self.get_config_value(self.instance_ip, 'max_connections')
        self.assertNotEqual(new_value, int(cur_value))
        self.assertNotEqual(updated_value, int(cur_value))

    @decorators.idempotent_id("280d09c6-b027-11ea-b87c-00224d6b7bc1")
    def test_replication(self):
        # Insert data for primary
        self.insert_data_replication(self.instance_ip, constants.DB_USER,
                                     constants.DB_PASS, constants.DB_NAME)

        # Create replica1
        LOG.info(f"Creating replica1 for instance {self.instance_id}")
        name = self.get_resource_name("replica-01")
        replica1 = self.create_instance(name, replica_of=self.instance_id)
        replica1_id = replica1['id']
        self.addCleanup(self.wait_for_instance_status, replica1_id,
                        need_delete=True, expected_status='DELETED')
        self.wait_for_instance_status(
            replica1_id,
            timeout=CONF.database.database_build_timeout * 2)
        replica1 = self.client.get_resource(
            "instances", replica1_id)['instance']
        replica1_ip = self.get_instance_ip(replica1)

        # Verify API response of primary
        ret = self.client.get_resource('instances', self.instance_id)
        self.assertIsNotNone(ret['instance'].get('replicas'))
        self.assertEqual(1, len(ret['instance']['replicas']))
        self.assertEqual(replica1_id,
                         ret['instance']['replicas'][0]['id'])

        # Verify API response of replica1
        ret = self.client.get_resource('instances', replica1_id)
        self.assertIsNotNone(ret['instance'].get('replica_of'))
        self.assertEqual(self.instance_id,
                         ret['instance']['replica_of']['id'])

        # Verify databases created in replica
        time.sleep(5)
        primary_dbs = self.get_databases(self.instance_id)
        replica_dbs = self.get_databases(replica1_id)
        self.assertEqual(len(primary_dbs), len(replica_dbs))

        # Create a new database in primary and verify in replica
        LOG.info(f"Creating database in instance {self.instance_id}")
        create_db = {"databases": [{"name": 'db_for_replication'}]}
        self.client.create_resource(f"instances/{self.instance_id}/databases",
                                    create_db, expected_status_code=202,
                                    need_response=False)
        time.sleep(5)
        new_primary_dbs = self.get_databases(self.instance_id)
        new_replica1_dbs = self.get_databases(replica1_id)
        self.assertEqual(len(new_primary_dbs), len(new_replica1_dbs))
        self.assertGreater(len(new_replica1_dbs), len(replica_dbs))
        new_db_names = [db['name'] for db in new_replica1_dbs]
        self.assertIn('db_for_replication', new_db_names)

        # Create replica2
        LOG.info(f"Creating replica2 for instance {self.instance_id}")
        name = self.get_resource_name("replica-02")
        replica2 = self.create_instance(name, replica_of=self.instance_id)
        replica2_id = replica2['id']
        self.addCleanup(self.wait_for_instance_status, replica2_id,
                        need_delete=True, expected_status='DELETED')
        self.wait_for_instance_status(
            replica2_id,
            timeout=CONF.database.database_build_timeout * 2)
        replica2 = self.client.get_resource(
            "instances", replica2_id)['instance']
        replica2_ip = self.get_instance_ip(replica2)

        # Verify API response of primary and replica2
        ret = self.client.get_resource('instances', self.instance_id)
        self.assertIsNotNone(ret['instance'].get('replicas'))
        self.assertEqual(2, len(ret['instance']['replicas']))
        replica_ids = [replica['id']
                       for replica in ret['instance']['replicas']]
        self.assertIn(replica1_id, replica_ids)
        self.assertIn(replica2_id, replica_ids)

        # Verify databases synced to replica2
        time.sleep(5)
        replica2_dbs = self.get_databases(replica2_id)
        replica2_db_names = [db['name'] for db in replica2_dbs]
        self.assertIn('db_for_replication', replica2_db_names)

        # Verify data synchronization on replica1 and replica2
        self.verify_data_replication(replica1_ip, constants.DB_USER,
                                     constants.DB_PASS, constants.DB_NAME)
        self.verify_data_replication(replica2_ip, constants.DB_USER,
                                     constants.DB_PASS, constants.DB_NAME)

        # Promote replica1 to primary
        LOG.info(f"Promoting replica1 {replica1_id} to primary")
        promote_primary = {
            "promote_to_replica_source": {}
        }
        self.client.create_resource(f"instances/{replica1_id}/action",
                                    promote_primary, expected_status_code=202,
                                    need_response=False)
        self.wait_for_instance_status(replica1_id)

        # Make sure to delete replicas first for clean up
        self.addCleanup(self.wait_for_instance_status, self.instance_id,
                        need_delete=True, expected_status='DELETED')
        self.addCleanup(self.wait_for_instance_status, replica2_id,
                        need_delete=True, expected_status='DELETED')

        # Verify API response of the new primary
        ret = self.client.get_resource('instances', replica1_id)
        self.assertIsNotNone(ret['instance'].get('replicas'))
        self.assertEqual(2, len(ret['instance']['replicas']))
        replica_ids = [replica['id']
                       for replica in ret['instance']['replicas']]
        self.assertEqual([self.instance_id, replica2_id], replica_ids)

        # Verify API response of replicas
        ret = self.client.get_resource('instances', replica2_id)
        self.assertIsNotNone(ret['instance'].get('replica_of'))
        self.assertEqual(replica1_id, ret['instance']['replica_of']['id'])

        # Insert data to new primary and verify in replicas
        self.insert_data_after_promote(replica1_ip, constants.DB_USER,
                                       constants.DB_PASS, constants.DB_NAME)
        time.sleep(5)
        self.verify_data_after_promote(self.instance_ip, constants.DB_USER,
                                       constants.DB_PASS, constants.DB_NAME)
        self.verify_data_after_promote(replica2_ip, constants.DB_USER,
                                       constants.DB_PASS, constants.DB_NAME)
