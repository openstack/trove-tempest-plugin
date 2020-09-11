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
from trove_tempest_plugin.tests.scenario import base_replication
from trove_tempest_plugin.tests import utils


class TestReplicationMySQL(base_replication.TestReplicationBase):
    datastore = 'mysql'

    def insert_data_replication(self, ip,
                                username=constants.DB_USER,
                                password=constants.DB_PASS,
                                database=constants.DB_NAME):
        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306/{database}'
        with utils.SQLClient(db_url) as db_client:
            cmds = [
                "CREATE TABLE Persons (ID int, String varchar(255));",
                "insert into Persons VALUES (1, 'replication');"
            ]
            db_client.mysql_execute(cmds)

    def verify_data_replication(self, ip,
                                username=constants.DB_USER,
                                password=constants.DB_PASS,
                                database=constants.DB_NAME):
        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306/{database}'
        with utils.SQLClient(db_url) as db_client:
            cmd = "select * from Persons;"
            ret = db_client.mysql_execute(cmd)
            keys = ret.keys()
            rows = ret.fetchall()
        self.assertEqual(1, len(rows))

        result = []
        for index in range(len(rows)):
            result.append(dict(zip(keys, rows[index])))
        expected = {'ID': 1, 'String': 'replication'}
        self.assert_single_item(result, **expected)

    def insert_data_after_promote(self, ip,
                                  username=constants.DB_USER,
                                  password=constants.DB_PASS,
                                  database=constants.DB_NAME):
        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306/{database}'
        with utils.SQLClient(db_url) as db_client:
            cmds = [
                "insert into Persons VALUES (2, 'promote');"
            ]
            db_client.mysql_execute(cmds)

    def verify_data_after_promote(self, ip,
                                  username=constants.DB_USER,
                                  password=constants.DB_PASS,
                                  database=constants.DB_NAME):
        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306/{database}'
        with utils.SQLClient(db_url) as db_client:
            cmd = "select * from Persons;"
            ret = db_client.mysql_execute(cmd)
            keys = ret.keys()
            rows = ret.fetchall()
        self.assertGreater(len(rows), 1)

        result = []
        for index in range(len(rows)):
            result.append(dict(zip(keys, rows[index])))
        expected = {'ID': 2, 'String': 'promote'}
        self.assert_single_item(result, **expected)

    def create_database(self, name, **kwargs):
        create_db = {"databases": [{"name": name}]}
        self.client.create_resource(f"instances/{self.instance_id}/databases",
                                    create_db, expected_status_code=202,
                                    need_response=False)

    @decorators.idempotent_id("280d09c6-b027-11ea-b87c-00224d6b7bc1")
    def test_replication(self):
        self.replication_test()


class TestReplicationPostgreSQL(base_replication.TestReplicationBase):
    datastore = 'postgresql'
    create_user = False
    enable_root = True

    def insert_data_replication(self, ip):
        db_url = (f'postgresql+psycopg2://root:{self.password}@'
                  f'{ip}:5432/postgres')

        with utils.SQLClient(db_url) as db_client:
            cmd = "CREATE DATABASE testdb;"
            db_client.pgsql_execute(cmd)

        db_url = (f'postgresql+psycopg2://root:{self.password}@'
                  f'{ip}:5432/testdb')
        with utils.SQLClient(db_url) as db_client:
            cmds = [
                "CREATE TABLE Persons (ID int, String varchar(255));",
                "insert into Persons VALUES (1, 'replication');"
            ]
            db_client.pgsql_execute(cmds)

    def verify_data_replication(self, ip):
        db_url = (f'postgresql+psycopg2://root:{self.password}@'
                  f'{ip}:5432/testdb')

        with utils.SQLClient(db_url) as db_client:
            cmd = "select * from Persons;"
            ret = db_client.pgsql_execute(cmd)
            keys = ret.keys()
            rows = ret.fetchall()
        self.assertEqual(1, len(rows))

        result = []
        for index in range(len(rows)):
            result.append(dict(zip(keys, rows[index])))
        expected = {'id': 1, 'string': 'replication'}
        self.assert_single_item(result, **expected)

    def insert_data_after_promote(self, ip):
        db_url = (f'postgresql+psycopg2://root:{self.password}@'
                  f'{ip}:5432/testdb')
        with utils.SQLClient(db_url) as db_client:
            cmds = [
                "insert into Persons VALUES (2, 'promote');"
            ]
            db_client.pgsql_execute(cmds)

    def verify_data_after_promote(self, ip):
        db_url = (f'postgresql+psycopg2://root:{self.password}@'
                  f'{ip}:5432/testdb')

        with utils.SQLClient(db_url) as db_client:
            cmd = "select * from Persons;"
            ret = db_client.pgsql_execute(cmd)
            keys = ret.keys()
            rows = ret.fetchall()
        self.assertGreater(len(rows), 1)

        result = []
        for index in range(len(rows)):
            result.append(dict(zip(keys, rows[index])))
        expected = {'id': 2, 'string': 'promote'}
        self.assert_single_item(result, **expected)

    def get_databases(self, instance_id, ip="", **kwargs):
        db_url = (f'postgresql+psycopg2://root:{self.password}@'
                  f'{ip}:5432/postgres')

        with utils.SQLClient(db_url) as db_client:
            cmd = "SELECT datname FROM pg_catalog.pg_database WHERE " \
                  "(datistemplate ISNULL OR datistemplate = false);"
            ret = db_client.pgsql_execute(cmd)
            rows = ret.fetchall()

        dbs = []
        for row in rows:
            dbs.append({'name': row[0]})

        return dbs

    def create_database(self, name, ip=""):
        db_url = (f'postgresql+psycopg2://root:{self.password}@'
                  f'{ip}:5432/postgres')

        with utils.SQLClient(db_url) as db_client:
            cmd = f"CREATE DATABASE {name};"
            db_client.pgsql_execute(cmd)

    @decorators.idempotent_id("2f37f064-f418-11ea-a950-00224d6b7bc1")
    def test_replication(self):
        self.replication_test()
