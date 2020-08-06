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

from trove_tempest_plugin.tests.scenario import base_actions
from trove_tempest_plugin.tests import utils

LOG = logging.getLogger(__name__)


class TestInstanceActionsMySQL(base_actions.TestInstanceActionsBase):
    datastore = 'mysql'

    @classmethod
    def init_db(cls, ip, username, password, database):
        LOG.info(f"Initializing database {database} on {ip}")

        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306/{database}'
        db_client = utils.SQLClient(db_url)

        cmds = [
            "CREATE TABLE Persons (ID int, String varchar(255));",
        ]
        db_client.execute(cmds)

    def insert_data_upgrade(self, ip, username, password, database):
        LOG.info(f"Inserting data to database {database} on {ip} for "
                 f"datastore upgrade")

        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306/{database}'
        db_client = utils.SQLClient(db_url)

        cmds = [
            "insert into Persons VALUES (99, 'Upgrade');"
        ]
        db_client.execute(cmds)

    def verify_data_upgrade(self, ip, username, password, database):
        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306/{database}'
        db_client = utils.SQLClient(db_url)

        cmd = "select * from Persons;"
        ret = db_client.execute(cmd)
        keys = ret.keys()
        rows = ret.fetchall()
        self.assertGreaterEqual(len(rows), 1)

        result = []
        for index in range(len(rows)):
            result.append(dict(zip(keys, rows[index])))
        expected = {'ID': 99, 'String': 'Upgrade'}
        self.assert_single_item(result, **expected)

    def insert_data_before_rebuild(self, ip, username, password, database):
        LOG.info(f"Inserting data to database {database} on {ip} "
                 f"before rebuilding instance")

        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306/{database}'
        db_client = utils.SQLClient(db_url)

        cmds = [
            "CREATE TABLE Rebuild (ID int, String varchar(255));",
            "insert into Rebuild VALUES (1, 'rebuild-data');"
        ]
        db_client.execute(cmds)

    def verify_data_after_rebuild(self, ip, username, password, database):
        LOG.info(f"Verifying data in database {database} on {ip} "
                 f"after rebuilding instance")

        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306/{database}'
        db_client = utils.SQLClient(db_url)

        cmd = "select * from Rebuild;"
        ret = db_client.execute(cmd)
        keys = ret.keys()
        rows = ret.fetchall()
        self.assertEqual(1, len(rows))

        actual = dict(zip(keys, rows[0]))
        expected = {'ID': 1, 'String': 'rebuild-data'}
        self.assertEqual(expected, actual)


class TestInstanceActionsMariaDB(TestInstanceActionsMySQL):
    datastore = 'mariadb'
