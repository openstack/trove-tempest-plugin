# Copyright 2019 Catalyst Cloud Ltd.
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
from oslo_utils import netutils
from tempest.lib import decorators

from trove_tempest_plugin.tests import base as trove_base
from trove_tempest_plugin.tests import utils

LOG = logging.getLogger(__name__)


class TestInstanceBasicMySQLBase(trove_base.BaseTroveTest):
    def _access_db(self, ip, username='test_user', password='password'):
        db_engine = utils.LocalSqlClient.init_engine(ip, username, password)
        db_client = utils.LocalSqlClient(db_engine)

        LOG.info('Trying to access the database %s', ip)

        with db_client:
            cmd = "SELECT 1;"
            db_client.execute(cmd)

    @decorators.idempotent_id("40cf38ce-cfbf-11e9-8760-1458d058cfb2")
    def test_database_access(self):
        res = self.client.get_resource("instances", self.instance_id)
        ips = res["instance"].get('ip', [])

        # TODO(lxkong): IPv6 needs to be tested.
        v4_ip = None
        for ip in ips:
            if netutils.is_valid_ipv4(ip):
                v4_ip = ip
                break

        self.assertIsNotNone(v4_ip)
        time.sleep(5)
        self._access_db(v4_ip)
