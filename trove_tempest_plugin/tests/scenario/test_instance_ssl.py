# Copyright 2026 PS Cloud Services.
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

import os
import tempfile
from trove_tempest_plugin.tests import constants
from trove_tempest_plugin.tests.scenario import base_ssl
from trove_tempest_plugin.tests import utils

LOG = logging.getLogger(__name__)
CONF = config.CONF


class TestInstanceSSLMySQL(base_ssl.TestInstanceSSLMySQLBase):
    datastore = 'mysql'


class TestInstanceSSLMariaDB(base_ssl.TestInstanceSSLMySQLBase):
    datastore = 'mariadb'


class TestInstanceSSLPostgreSQL(base_ssl.TestInstanceSSLBase):
    datastore = 'postgresql'

    def connect_plain(self, ip):
        db_url = (
            f"postgresql+psycopg2://{constants.DB_USER}:{constants.DB_PASS}"
            f"@{ip}:5432/{constants.DB_NAME}"
            f"?sslmode=disable"
        )

        try:
            with utils.SQLClient(db_url) as db_client:
                db_client.pgsql_execute("SELECT 1;")
            return True
        except Exception:
            return False

    def connect_ssl(self, ip, p12):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(p12['cas'][0])
            ca_cert_path = f.name

        db_url = (
            f"postgresql+psycopg2://{constants.DB_USER}:{constants.DB_PASS}"
            f"@{ip}:5432/{constants.DB_NAME}"
            f"?sslmode=verify-ca&sslrootcert={ca_cert_path}"
        )

        try:
            with utils.SQLClient(db_url) as db_client:
                result = db_client.pgsql_execute(
                    """
                    SELECT ssl
                    FROM pg_stat_ssl
                    WHERE pid = pg_backend_pid();
                    """
                )
                row = result.fetchone()

            return bool(row and row[0] is True)
        except Exception as e:
            LOG.warning(
                'Exception during SSL check: %s', e, exc_info=CONF.debug)
            return False
        finally:
            if os.path.exists(ca_cert_path):
                os.remove(ca_cert_path)

    def connect_ssl_client_cert(self, ip, p12):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as ca:
            ca.write(p12['cas'][0])
            ca_path = ca.name

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as cert:
            cert.write(p12['client_cert'])
            cert_path = cert.name

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as key:
            key.write(p12['client_key'])
            key_path = key.name

        db_url = (
            f"postgresql+psycopg2://{constants.DB_USER}"
            f"@{ip}:5432/{constants.DB_NAME}"
            f"?sslmode=verify-full"
        )

        connect_args = {
            "sslrootcert": ca_path,
            "sslcert": cert_path,
            "sslkey": key_path,
        }

        try:
            with utils.SQLClient(db_url, connect_args=connect_args) as db:
                db.pgsql_execute("SELECT 1;")
            return True
        except Exception as e:
            LOG.warning(
                'Exception during SSL check: %s', e, exc_info=CONF.debug)
            return False
        finally:
            for path in [ca_path, cert_path, key_path]:
                if os.path.exists(path):
                    os.remove(path)

    def connect_mtls_with_password(self, ip, p12):
        # In mtls mode postgresql allow any password, so
        # this check is meaningless.
        pass
