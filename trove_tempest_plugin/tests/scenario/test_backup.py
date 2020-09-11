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
from tempest.lib import decorators

from trove_tempest_plugin.tests import constants
from trove_tempest_plugin.tests.scenario import base_backup
from trove_tempest_plugin.tests import utils


class TestBackupMySQL(base_backup.TestBackupBase):
    datastore = 'mysql'

    @classmethod
    def insert_data(cls, ip, username=constants.DB_USER,
                    password=constants.DB_PASS, database=constants.DB_NAME,
                    **kwargs):
        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306/{database}'
        with utils.SQLClient(db_url) as db_client:
            cmds = [
                "CREATE TABLE Persons (ID int, String varchar(255));",
                "insert into Persons VALUES (1, 'Lingxian Kong');",
            ]
            db_client.mysql_execute(cmds)

    @classmethod
    def insert_data_inc(cls, ip, username=constants.DB_USER,
                        password=constants.DB_PASS, database=constants.DB_NAME,
                        **kwargs):
        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306/{database}'
        with utils.SQLClient(db_url) as db_client:
            cmds = [
                "insert into Persons VALUES (99, 'OpenStack');"
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
        expected = {'ID': 1, 'String': 'Lingxian Kong'}
        self.assertEqual(expected, result)

    def verify_data_inc(self, ip, username=constants.DB_USER,
                        password=constants.DB_PASS,
                        database=constants.DB_NAME):
        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306/{database}'
        with utils.SQLClient(db_url) as db_client:
            cmd = "select * from Persons;"
            ret = db_client.mysql_execute(cmd)
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

    @decorators.idempotent_id("b90626ae-f412-11ea-a950-00224d6b7bc1")
    def test_backup_full(self):
        self.backup_full_test()

    @decorators.idempotent_id("f8f985c2-ae02-11ea-b87c-00224d6b7bc1")
    def test_backup_incremental(self):
        self.backup_incremental_test()


class TestBackupPostgreSQL(base_backup.TestBackupBase):
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
                "INSERT INTO persons (id,string) VALUES (1, 'Lingxian Kong');",
            ]
            db_client.pgsql_execute(cmds)

    @classmethod
    def insert_data_inc(cls, ip):
        db_url = (f'postgresql+psycopg2://root:{cls.password}@'
                  f'{ip}:5432/testdb')
        with utils.SQLClient(db_url) as db_client:
            cmds = [
                "INSERT INTO persons (id,string) VALUES (99, 'OpenStack');"
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
        expected = {'id': 1, 'string': 'Lingxian Kong'}
        self.assertEqual(expected, result)

    def verify_data_inc(self, ip, username=constants.DB_USER,
                        password=constants.DB_PASS,
                        database=constants.DB_NAME):
        db_url = (f'postgresql+psycopg2://root:{self.root_password}@'
                  f'{ip}:5432/testdb')
        with utils.SQLClient(db_url) as db_client:
            cmd = "select * from persons;"
            ret = db_client.pgsql_execute(cmd)
            keys = ret.keys()
            rows = ret.fetchall()
        self.assertEqual(2, len(rows))

        actual = []
        for index in range(2):
            actual.append(dict(zip(keys, rows[index])))

        expected = [
            {'id': 1, 'string': 'Lingxian Kong'},
            {'id': 99, 'string': 'OpenStack'},
        ]
        self.assertEqual(expected, actual)

    @decorators.idempotent_id("e8339fce-f412-11ea-a950-00224d6b7bc1")
    def test_backup_full(self):
        self.backup_full_test()

    @decorators.idempotent_id("ec387400-f412-11ea-a950-00224d6b7bc1")
    def test_backup_incremental(self):
        self.backup_incremental_test()
