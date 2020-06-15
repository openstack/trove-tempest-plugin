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

LOG = logging.getLogger(__name__)
CONF = config.CONF


def get_db_version(ip, username=constants.DB_USER, password=constants.DB_PASS):
    LOG.info('Trying to access the database %s', ip)

    db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306'
    db_client = utils.SQLClient(db_url)

    cmd = "SELECT @@GLOBAL.innodb_version;"
    ret = db_client.execute(cmd)
    return ret.first()[0]


class TestInstanceActionsBase(trove_base.BaseTroveTest):
    @classmethod
    def init_db(cls, *args, **kwargs):
        pass

    def insert_data_upgrade(self, *args, **kwargs):
        pass

    def verify_data_upgrade(self, *args, **kwargs):
        pass

    @classmethod
    def resource_setup(cls):
        super(TestInstanceActionsBase, cls).resource_setup()

        # Initialize database
        cls.init_db(cls.instance_ip, constants.DB_USER, constants.DB_PASS,
                    constants.DB_NAME)

    @decorators.idempotent_id("be6dd514-27d6-11ea-a56a-98f2b3cc23a0")
    def test_instance_upgrade(self):
        cur_version = self.instance['datastore']['version']
        cfg_versions = CONF.database.pre_upgrade_datastore_versions
        ds_version = cfg_versions.get(self.datastore)
        if not ds_version:
            # Fall back to the instance datastore version. In this case, we are
            # still testing the upgrade API but the datastore version doesn't
            # change actually.
            ds_version = cur_version

        name = self.get_resource_name("pre-upgrade")
        LOG.info(f'Creating instance {name} with datastore version '
                 f'{ds_version} for upgrade')
        instance = self.create_instance(name=name,
                                        datastore_version=ds_version)
        self.wait_for_instance_status(instance['id'])
        instance = self.client.get_resource(
            "instances", instance['id'])['instance']
        instance_ip = self.get_instance_ip(instance)

        # Insert data before upgrading
        self.init_db(instance_ip, constants.DB_USER, constants.DB_PASS,
                     constants.DB_NAME)
        self.insert_data_upgrade(instance_ip, constants.DB_USER,
                                 constants.DB_PASS, constants.DB_NAME)

        new_version = cur_version
        LOG.info(f"Upgrading instance {instance['id']} using datastore "
                 f"{new_version}")
        body = {"instance": {"datastore_version": new_version}}
        self.client.patch_resource('instances', instance['id'], body)

        # Wait in case the instance status hasn't changed yet.
        time.sleep(5)
        self.wait_for_instance_status(instance['id'])
        actual = get_db_version(instance_ip)
        self.assertEqual(new_version, actual)

        self.verify_data_upgrade(instance_ip, constants.DB_USER,
                                 constants.DB_PASS, constants.DB_NAME)

        # Delete the new instance explicitly to avoid too many instances
        # during the test.
        self.wait_for_instance_status(instance['id'],
                                      expected_status="DELETED",
                                      need_delete=True)
