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

from trove_tempest_plugin.tests.scenario import base_backup
from trove_tempest_plugin.tests import utils

LOG = logging.getLogger(__name__)


class TestBackupMySQL(base_backup.TestBackupBase):
    datastore = 'mysql'

    @classmethod
    def insert_data(cls, ip, username, password, database, **kwargs):
        LOG.info(f"Inserting data to database {database} on {ip}")

        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306/{database}'
        db_client = utils.SQLClient(db_url)

        cmds = [
            "CREATE TABLE Persons (ID int, String varchar(255));",
            "insert into Persons VALUES (1, 'Lingxian Kong');",
        ]
        db_client.execute(cmds)

    @classmethod
    def insert_data_inc(cls, ip, username, password, database, **kwargs):
        LOG.info(f"Inserting data to database {database} on {ip} for "
                 f"incremental backup")

        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306/{database}'
        db_client = utils.SQLClient(db_url)

        cmds = [
            "insert into Persons VALUES (99, 'OpenStack');"
        ]
        db_client.execute(cmds)

    def verify_data(self, ip, username, password, database):
        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306/{database}'
        db_client = utils.SQLClient(db_url)

        cmd = "select * from Persons;"
        ret = db_client.execute(cmd)
        keys = ret.keys()
        rows = ret.fetchall()
        self.assertEqual(1, len(rows))

        result = dict(zip(keys, rows[0]))
        expected = {'ID': 1, 'String': 'Lingxian Kong'}
        self.assertEqual(expected, result)

    def verify_data_inc(self, ip, username, password, database):
        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306/{database}'
        db_client = utils.SQLClient(db_url)

        cmd = "select * from Persons;"
        ret = db_client.execute(cmd)
        keys = ret.keys()
        rows = ret.fetchall()
        self.assertEqual(2, len(rows))

        actual = []
        for index in range(2):
            actual.append(dict(zip(keys, rows[index])))

        expected = [
            {'ID': 1, 'String': 'Lingxian Kong'},
            {'ID': 99, 'String': 'OpenStack'},
        ]
        self.assertEqual(expected, actual)
