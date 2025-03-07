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

from tempest.lib import decorators

from trove_tempest_plugin.tests import constants
from trove_tempest_plugin.tests.scenario import base_cinder_backup
from trove_tempest_plugin.tests import utils


class TestCinderBakcupMySQL(base_cinder_backup.TestCinderBackupBase):
    datastore = 'mysql'

    @classmethod
    def insert_data(cls, ip, username=constants.DB_USER,
                    password=constants.DB_PASS, database=constants.DB_NAME,
                    **kwargs):
        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306/{database}'
        with utils.SQLClient(db_url) as db_client:
            cmds = [
                "CREATE TABLE Persons (ID int, String varchar(255));",
                "insert into Persons VALUES (1, 'OpenStack');",
            ]
            db_client.mysql_execute(cmds)

    def verify_data(self, ip, username=constants.DB_USER,
                    password=constants.DB_PASS, database=constants.DB_NAME):
        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306/{database}'
        with utils.SQLClient(db_url) as db_client:
            cmd = "select * from Persons;"
            ret = db_client.mysql_execute(cmd)
            keys = ret.keys()
            rows = ret.fetchall()
        self.assertEqual(1, len(rows))

        result = dict(zip(keys, rows[0]))
        expected = {'ID': 1, 'String': 'OpenStack'}
        self.assertEqual(expected, result)

    @decorators.idempotent_id('2d5e2c8d-6f7c-44c1-8944-260fc684af40')
    def test_backup_cinder(self):
        self.backup_test()


class TestCinderBackupPostgreSQL(base_cinder_backup.TestCinderBackupBase):
    datastore = 'postgresql'
    create_user = False
    enable_root = True
    root_password = ""

    @classmethod
    def insert_data(cls, ip):
        db_url = (f'postgresql+psycopg2://root:{cls.password}@'
                  f'{ip}:5432/postgres')
        with utils.SQLClient(db_url) as db_client:
            cmd = "CREATE DATABASE testdb;"
            db_client.pgsql_execute(cmd)

        db_url = (f'postgresql+psycopg2://root:{cls.password}@'
                  f'{ip}:5432/testdb')
        with utils.SQLClient(db_url) as db_client:
            cmds = [
                "CREATE TABLE persons (id INT PRIMARY KEY NOT NULL, "
                "string VARCHAR(255));",
                "INSERT INTO persons (id,string) VALUES (1, 'OpenStack');",
            ]
            db_client.pgsql_execute(cmds)

    def verify_data(self, ip):
        db_url = (f'postgresql+psycopg2://root:{self.root_password}@'
                  f'{ip}:5432/testdb')
        with utils.SQLClient(db_url) as db_client:
            cmd = "select * from persons;"
            ret = db_client.pgsql_execute(cmd)
            keys = ret.keys()
            rows = ret.fetchall()
        self.assertEqual(1, len(rows))

        result = dict(zip(keys, rows[0]))
        expected = {'id': 1, 'string': 'OpenStack'}
        self.assertEqual(expected, result)

    @decorators.idempotent_id('4dab0bbf-06c2-4fbd-89fb-16dece9224f2')
    def test_backup_cinder(self):
        self.backup_test()


class TestCinderBackupMariaDB(TestCinderBakcupMySQL):
    datastore = 'mariadb'
