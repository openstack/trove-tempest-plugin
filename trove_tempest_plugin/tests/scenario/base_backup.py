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
from tempest import config
from tempest.lib import decorators

from trove_tempest_plugin.tests import base as trove_base
from trove_tempest_plugin.tests import constants

LOG = logging.getLogger(__name__)
CONF = config.CONF


class TestBackupBase(trove_base.BaseTroveTest):
    @classmethod
    def insert_data(cls, *args, **kwargs):
        pass

    @classmethod
    def insert_data_inc(cls, *args, **kwargs):
        pass

    def verify_data(self, *args, **kwargs):
        pass

    def verify_data_inc(self, *args, **kwargs):
        pass

    @classmethod
    def resource_setup(cls):
        super(TestBackupBase, cls).resource_setup()

        # Trove will automatically create a swift container for backup. We need
        # to make sure there is no swift container left for test user after
        # testing.
        if CONF.database.remove_swift_account:
            cls.addClassResourceCleanup(cls.delete_swift_account)

        # Insert some data to the current db instance
        cls.insert_data(cls.instance_ip, constants.DB_USER, constants.DB_PASS,
                        constants.DB_NAME)

        # Create a backup that is shared within this test class.
        name = cls.get_resource_name("backup")
        backup = cls.create_backup(cls.instance_id, name)
        cls.wait_for_backup_status(backup['id'])
        cls.backup = cls.client.get_resource("backups", backup['id'])['backup']

    @decorators.idempotent_id("bdff1ae0-ad6c-11ea-b87c-00224d6b7bc1")
    def test_backup_full(self):
        # Restore from backup
        LOG.info(f'Creating a new instance using the backup '
                 f'{self.backup["id"]}')
        name = self.get_resource_name("restore")
        restore_instance = self.create_instance(
            name,
            datastore_version=self.backup['datastore']['version'],
            backup_id=self.backup['id']
        )
        self.wait_for_instance_status(restore_instance['id'])
        restore_instance = self.client.get_resource(
            "instances", restore_instance['id'])['instance']
        restore_instance_ip = self.get_instance_ip(restore_instance)

        self.verify_data(restore_instance_ip, constants.DB_USER,
                         constants.DB_PASS, constants.DB_NAME)

        # Delete the new instance explicitly to avoid too many instances
        # during the test.
        self.wait_for_instance_status(restore_instance['id'],
                                      expected_status="DELETED",
                                      need_delete=True)

    @decorators.idempotent_id("f8f985c2-ae02-11ea-b87c-00224d6b7bc1")
    def test_backup_incremental(self):
        # Insert some data
        self.insert_data_inc(self.instance_ip, constants.DB_USER,
                             constants.DB_PASS, constants.DB_NAME)

        # Create a second backup
        LOG.info(f"Creating an incremental backup based on "
                 f"{self.backup['id']}")
        name = self.get_resource_name("backup-inc")
        backup_inc = self.create_backup(
            self.instance_id, name, incremental=True,
            parent_id=self.backup['id']
        )
        self.wait_for_backup_status(backup_inc['id'])

        # Restore from backup
        LOG.info(f"Creating a new instance using the backup "
                 f"{backup_inc['id']}")
        name = self.get_resource_name("restore-inc")
        restore_instance = self.create_instance(
            name,
            datastore_version=backup_inc['datastore']['version'],
            backup_id=backup_inc['id']
        )
        self.wait_for_instance_status(restore_instance['id'])
        restore_instance = self.client.get_resource(
            "instances", restore_instance['id'])['instance']
        restore_instance_ip = self.get_instance_ip(restore_instance)

        self.verify_data_inc(restore_instance_ip, constants.DB_USER,
                             constants.DB_PASS, constants.DB_NAME)

        # Delete the new instance explicitly to avoid too many instances
        # during the test.
        self.wait_for_instance_status(restore_instance['id'],
                                      expected_status="DELETED",
                                      need_delete=True)
