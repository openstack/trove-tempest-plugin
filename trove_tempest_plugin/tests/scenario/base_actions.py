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

from trove_tempest_plugin.tests import base as trove_base

LOG = logging.getLogger(__name__)
CONF = config.CONF


class TestInstanceActionsBase(trove_base.BaseTroveTest):
    @classmethod
    def init_db(cls, *args, **kwargs):
        pass

    def insert_data_upgrade(self, *args, **kwargs):
        pass

    def verify_data_upgrade(self, *args, **kwargs):
        pass

    def insert_data_before_rebuild(self, *args, **kwargs):
        pass

    def verify_data_after_rebuild(self, *args, **kwargs):
        pass

    def get_db_version(self):
        pass

    def get_config_value(self, ip, option, **kwargs):
        pass

    @classmethod
    def resource_setup(cls):
        super(TestInstanceActionsBase, cls).resource_setup()

        # Initialize database
        LOG.info(f"Initializing data on {cls.instance_ip}")
        cls.init_db(cls.instance_ip)

    def instance_upgrade_test(self):
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
                                        datastore_version=ds_version,
                                        create_user=self.create_user)
        self.wait_for_instance_status(instance['id'])
        instance = self.client.get_resource(
            "instances", instance['id'])['instance']
        instance_ip = self.get_instance_ip(instance)

        # Insert data before upgrading
        LOG.info(f"Initializing data on {instance_ip} before upgrade")
        self.init_db(instance_ip)
        LOG.info(f"Inserting data on {instance_ip} before upgrade")
        self.insert_data_upgrade(instance_ip)

        new_version = cur_version
        LOG.info(f"Upgrading instance {instance['id']} using datastore "
                 f"{new_version}")
        body = {"instance": {"datastore_version": new_version}}
        self.client.patch_resource('instances', instance['id'], body)
        self.wait_for_instance_status(instance['id'])

        LOG.info(f"Getting database version on {instance_ip}")
        actual = self.get_db_version(instance_ip)
        self.assertEqual(new_version, actual)

        LOG.info(f"Verifying data on {instance_ip} after upgrade")
        self.verify_data_upgrade(instance_ip)

        # Delete the new instance explicitly to avoid too many instances
        # during the test.
        self.wait_for_instance_status(instance['id'],
                                      expected_status="DELETED",
                                      need_delete=True)

    def resize_test(self):
        # Resize flavor
        LOG.info(f"Resizing flavor to {CONF.database.resize_flavor_id} for "
                 f"instance {self.instance_id}")
        resize_flavor = {
            "resize": {
                "flavorRef": CONF.database.resize_flavor_id
            }
        }
        self.client.create_resource(f"instances/{self.instance_id}/action",
                                    resize_flavor, expected_status_code=202,
                                    need_response=False)
        self.wait_for_instance_status(self.instance_id)

        # Verify Trove flavor
        ret = self.client.get_resource('instances', self.instance_id)
        self.assertEqual(CONF.database.resize_flavor_id,
                         ret['instance']['flavor']['id'])

        # Verify Nova flavor
        params = {
            'all_tenants': True,
            'detail': True,
            'name': self.instance['name']
        }
        servers = self.admin_server_client.list_servers(**params)['servers']
        self.assertEqual(1, len(servers))
        self.assertEqual(CONF.database.resize_flavor_id,
                         servers[0]['flavor']['id'])

        # Resize volume
        LOG.info(f"Resizing volume to 2 for instance {self.instance_id}")
        resize_volume = {
            "resize": {
                "volume": {
                    "size": 2
                }
            }
        }
        self.client.create_resource(f"instances/{self.instance_id}/action",
                                    resize_volume, expected_status_code=202,
                                    need_response=False)
        self.wait_for_instance_status(self.instance_id)

        # Verify Trove volume
        ret = self.client.get_resource('instances', self.instance_id)
        self.assertEqual(2, ret['instance']['volume']['size'])

    def rebuild_test(self, config_values, config_need_restart=False):
        LOG.info(f"Inserting data on {self.instance_ip} before rebuilding")
        self.insert_data_before_rebuild(self.instance_ip)

        # Create configuration before rebuild
        config_name = self.get_resource_name('config')
        LOG.info(f"Creating new configuration {config_name} for rebuild")
        config = self.create_config(
            config_name, config_values, self.datastore,
            self.instance['datastore']['version'])
        config_id = config['configuration']['id']
        self.addCleanup(self.client.delete_resource, 'configurations',
                        config_id, ignore_notfound=True)
        # Attach the configuration
        LOG.info(f"Attaching config {config_id} to instance "
                 f"{self.instance_id}")
        self.attach_config(self.instance_id, config_id)
        self.addCleanup(self.detach_config, self.instance_id)
        if config_need_restart:
            LOG.info(f"Restarting instance {self.instance_id}")
            self.restart_instance(self.instance_id)
        # Verify the config before rebuild
        key = list(config_values.keys())[0]
        value = list(config_values.values())[0]
        LOG.info(f"Getting config value for {key} on {self.instance_ip}")
        cur_value = self.get_config_value(self.instance_ip, key)
        self.assertEqual(value, cur_value)

        LOG.info(f"Rebuilding instance {self.instance_id} with image "
                 f"{CONF.database.rebuild_image_id}")
        self.rebuild_instance(self.instance_id, CONF.database.rebuild_image_id)

        LOG.info(f"Verifying data on {self.instance_ip} after rebuilding")
        self.verify_data_after_rebuild(self.instance_ip)

        # Verify configuration before rebuild
        LOG.info(f"Verifying config {key} on {self.instance_ip} after "
                 f"rebuilding")
        cur_value = self.get_config_value(self.instance_ip, key)
        self.assertEqual(value, cur_value)
