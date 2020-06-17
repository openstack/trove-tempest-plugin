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
import time

from oslo_log import log as logging
from tempest import config
from tempest.lib import decorators

from trove_tempest_plugin.tests import base as trove_base
from trove_tempest_plugin.tests import constants
from trove_tempest_plugin.tests import utils

CONF = config.CONF
LOG = logging.getLogger(__name__)


class TestReplicationBase(trove_base.BaseTroveTest):
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

        # Make sure to delete replicas first for clean up, in case failure
        # happens when replica1 is still the primary.
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
        self.assertCountEqual([self.instance_id, replica2_id], replica_ids)

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

        # Detach original primary from the replication cluster
        LOG.info(f"Detaching replica {self.instance_id} from the replication "
                 f"cluster")
        detach_replica = {
            "instance": {
                "replica_of": ""
            }
        }
        self.client.patch_resource('instances', self.instance_id,
                                   detach_replica)
        self.wait_for_instance_status(self.instance_id)

        # Verify original primary
        ret = self.client.get_resource('instances', self.instance_id)
        self.assertIsNone(ret['instance'].get('replicas'))
        self.assertIsNone(ret['instance'].get('replica_of'))
