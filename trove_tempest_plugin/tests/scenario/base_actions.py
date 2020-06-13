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
from tempest.lib import decorators

from trove_tempest_plugin.tests import base as trove_base
from trove_tempest_plugin.tests import utils

LOG = logging.getLogger(__name__)


def get_db_version(ip, username='test_user', password='password'):
    LOG.info('Trying to access the database %s', ip)

    db_url = f'mysql+pymysql://{username}:{password}@{ip}:3306'
    db_engine = utils.init_engine(db_url)
    db_client = utils.SQLClient(db_engine)

    cmd = "SELECT @@GLOBAL.innodb_version;"
    ret = db_client.execute(cmd)
    return ret.first()[0]


class TestInstanceActionsBase(trove_base.BaseTroveTest):
    @decorators.idempotent_id("be6dd514-27d6-11ea-a56a-98f2b3cc23a0")
    def test_instance_upgrade(self):
        datastore = self.instance['datastore']['type']
        version = self.instance['datastore']['version']
        new_version = version
        datastore = self.client.get_resource("datastores", datastore)
        for v in datastore['datastore']['versions']:
            if v['name'] != version:
                new_version = v['name']
                break

        LOG.info('Using datastore %s for instance upgrading', new_version)

        body = {
            "instance": {
                "datastore_version": new_version
            }
        }
        self.client.patch_resource('instances', self.instance_id, body)

        time.sleep(3)
        self.wait_for_instance_status(self.instance_id)

        time.sleep(3)
        actual = get_db_version(self.instance_ip)

        self.assertEqual(actual, new_version)
