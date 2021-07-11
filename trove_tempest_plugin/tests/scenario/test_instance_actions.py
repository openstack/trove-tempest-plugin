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
from tempest import config
from tempest.lib import decorators
import testtools

from trove_tempest_plugin.tests import constants
from trove_tempest_plugin.tests.scenario import base_actions
from trove_tempest_plugin.tests import utils

CONF = config.CONF


class InstanceActionsMySQLBase(base_actions.TestInstanceActionsBase):
    @classmethod
    def init_db(cls, ip, username=constants.DB_USER,
                password=constants.DB_PASS, database=constants.DB_NAME):
        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306/{database}'
        with utils.SQLClient(db_url) as db_client:
            cmds = [
                "CREATE TABLE Persons (ID int, String varchar(255));",
            ]
            db_client.mysql_execute(cmds)

    def insert_data_upgrade(self, ip,
                            username=constants.DB_USER,
                            password=constants.DB_PASS,
                            database=constants.DB_NAME):
        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306/{database}'
        with utils.SQLClient(db_url) as db_client:
            cmds = [
                "insert into Persons VALUES (99, 'Upgrade');"
            ]
            db_client.mysql_execute(cmds)

    def verify_data_upgrade(self, ip,
                            username=constants.DB_USER,
                            password=constants.DB_PASS,
                            database=constants.DB_NAME):
        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306/{database}'
        with utils.SQLClient(db_url) as db_client:
            cmd = "select * from Persons;"
            ret = db_client.mysql_execute(cmd)
            keys = ret.keys()
            rows = ret.fetchall()
        self.assertGreaterEqual(len(rows), 1)

        result = []
        for index in range(len(rows)):
            result.append(dict(zip(keys, rows[index])))
        expected = {'ID': 99, 'String': 'Upgrade'}
        self.assert_single_item(result, **expected)

    def insert_data_before_rebuild(self, ip,
                                   username=constants.DB_USER,
                                   password=constants.DB_PASS,
                                   database=constants.DB_NAME):
        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306/{database}'
        with utils.SQLClient(db_url) as db_client:
            cmds = [
                "CREATE TABLE Rebuild (ID int, String varchar(255));",
                "insert into Rebuild VALUES (1, 'rebuild-data');"
            ]
            db_client.mysql_execute(cmds)

    def verify_data_after_rebuild(self, ip,
                                  username=constants.DB_USER,
                                  password=constants.DB_PASS,
                                  database=constants.DB_NAME):
        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306/{database}'
        with utils.SQLClient(db_url) as db_client:
            cmd = "select * from Rebuild;"
            ret = db_client.mysql_execute(cmd)
            keys = ret.keys()
            rows = ret.fetchall()
        self.assertEqual(1, len(rows))

        actual = dict(zip(keys, rows[0]))
        expected = {'ID': 1, 'String': 'rebuild-data'}
        self.assertEqual(expected, actual)

    def get_db_version(self, ip, username=constants.DB_USER,
                       password=constants.DB_PASS):
        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306'
        with utils.SQLClient(db_url) as db_client:
            cmd = "SELECT @@GLOBAL.innodb_version;"
            ret = db_client.mysql_execute(cmd)
            return ret.first()[0]

    def get_config_value(self, ip, option, username=constants.DB_USER,
                         password=constants.DB_PASS):
        db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306'
        with utils.SQLClient(db_url) as db_client:
            cmd = f"show variables where Variable_name in ('{option}');"
            ret = db_client.mysql_execute(cmd)
            rows = ret.fetchall()
        self.assertEqual(1, len(rows))
        return int(rows[0][1])


class TestInstanceActionsMySQL(InstanceActionsMySQLBase):
    datastore = 'mysql'

    @decorators.idempotent_id("be6dd514-27d6-11ea-a56a-98f2b3cc23a0")
    @testtools.skipUnless(
        'mysql' in CONF.database.pre_upgrade_datastore_versions,
        'Datastore upgrade is disabled.')
    def test_instance_upgrade(self):
        self.instance_upgrade_test()

    @decorators.idempotent_id("27914e82-b061-11ea-b87c-00224d6b7bc1")
    def test_resize(self):
        self.resize_test()

    @decorators.idempotent_id("8d4d675c-d829-11ea-b87c-00224d6b7bc1")
    @testtools.skipUnless(CONF.database.rebuild_image_id,
                          'Image for rebuild not configured.')
    def test_rebuild(self):
        config_values = {"max_connections": 555}
        self.rebuild_test(config_values)


class TestInstanceActionsMariaDB(InstanceActionsMySQLBase):
    datastore = 'mariadb'

    @decorators.idempotent_id("f7a0fef6-f413-11ea-a950-00224d6b7bc1")
    @testtools.skipUnless(
        'mariadb' in CONF.database.pre_upgrade_datastore_versions,
        'Datastore upgrade is disabled.')
    def test_instance_upgrade(self):
        self.instance_upgrade_test()

    @decorators.idempotent_id("fb89d402-f413-11ea-a950-00224d6b7bc1")
    def test_resize(self):
        self.resize_test()

    @decorators.idempotent_id("ff34768e-f413-11ea-a950-00224d6b7bc1")
    @testtools.skipUnless(CONF.database.rebuild_image_id,
                          'Image for rebuild not configured.')
    def test_rebuild(self):
        config_values = {"max_connections": 555}
        self.rebuild_test(config_values)


class TestInstanceActionsPostgreSQL(base_actions.TestInstanceActionsBase):
    datastore = 'postgresql'
    create_user = False
    enable_root = True

    @classmethod
    def init_db(cls, ip):
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
            ]
            db_client.pgsql_execute(cmds)

    def insert_data_upgrade(self, ip):
        db_url = (f'postgresql+psycopg2://root:{self.password}@'
                  f'{ip}:5432/testdb')
        with utils.SQLClient(db_url) as db_client:
            cmds = [
                "insert into Persons VALUES (99, 'Upgrade');"
            ]
            db_client.pgsql_execute(cmds)

    def verify_data_upgrade(self, ip):
        db_url = (f'postgresql+psycopg2://root:{self.password}@'
                  f'{ip}:5432/testdb')
        with utils.SQLClient(db_url) as db_client:
            cmd = "select * from Persons;"
            ret = db_client.pgsql_execute(cmd)
            keys = ret.keys()
            rows = ret.fetchall()
        self.assertGreaterEqual(len(rows), 1)

        result = []
        for index in range(len(rows)):
            result.append(dict(zip(keys, rows[index])))
        expected = {'id': 99, 'string': 'Upgrade'}
        self.assert_single_item(result, **expected)

    def insert_data_before_rebuild(self, ip):
        db_url = (f'postgresql+psycopg2://root:{self.password}@'
                  f'{ip}:5432/testdb')
        with utils.SQLClient(db_url) as db_client:
            cmds = [
                "CREATE TABLE Rebuild (ID int, String varchar(255));",
                "insert into Rebuild VALUES (1, 'rebuild-data');"
            ]
            db_client.pgsql_execute(cmds)

    def verify_data_after_rebuild(self, ip):
        db_url = (f'postgresql+psycopg2://root:{self.password}@'
                  f'{ip}:5432/testdb')
        with utils.SQLClient(db_url) as db_client:
            cmd = "select * from Rebuild;"
            ret = db_client.pgsql_execute(cmd)
            keys = ret.keys()
            rows = ret.fetchall()
        self.assertEqual(1, len(rows))

        actual = dict(zip(keys, rows[0]))
        expected = {'id': 1, 'string': 'rebuild-data'}
        self.assertEqual(expected, actual)

    def get_db_version(self, ip, username=constants.DB_USER,
                       password=constants.DB_PASS):
        db_url = (f'postgresql+psycopg2://root:{self.password}@'
                  f'{ip}:5432/postgres')
        with utils.SQLClient(db_url) as db_client:
            cmd = "SHOW server_version;"
            ret = db_client.pgsql_execute(cmd)
            version = ret.first()[0]

        return version.split(' ')[0]

    def get_config_value(self, ip, option):
        db_url = (f'postgresql+psycopg2://root:{self.password}@'
                  f'{ip}:5432/postgres')
        with utils.SQLClient(db_url) as db_client:
            cmd = f"SELECT setting FROM pg_settings WHERE name='{option}';"
            ret = db_client.pgsql_execute(cmd)
            rows = ret.fetchall()

        self.assertEqual(1, len(rows))
        return int(rows[0][0])

    @decorators.idempotent_id("97f1e7ca-f415-11ea-a950-00224d6b7bc1")
    @testtools.skipUnless(
        'postgresql' in CONF.database.pre_upgrade_datastore_versions,
        'Datastore upgrade is disabled.')
    def test_instance_upgrade(self):
        self.instance_upgrade_test()

    @decorators.idempotent_id("9b940c00-f415-11ea-a950-00224d6b7bc1")
    def test_resize(self):
        self.resize_test()

    @decorators.idempotent_id("9ec5dd54-f415-11ea-a950-00224d6b7bc1")
    @testtools.skipUnless(CONF.database.rebuild_image_id,
                          'Image for rebuild not configured.')
    def test_rebuild(self):
        config_values = {"max_connections": 101}
        self.rebuild_test(config_values, config_need_restart=True)
