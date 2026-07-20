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

import abc
import base64
import os
import pymysql
import ssl
import tempfile
import testtools

from oslo_log import log as logging
from tempest import config
from tempest.lib import decorators
from tempest.lib import exceptions
from trove_tempest_plugin.tests import base as trove_base
from trove_tempest_plugin.tests import constants
from trove_tempest_plugin.tests import utils

CONF = config.CONF
LOG = logging.getLogger(__name__)


class TestInstanceSSLBase(trove_base.BaseTroveTest):
    def assertPlainConnection(self, ip):
        self.assertTrue(
            self.connect_plain(ip),
            'Plain connection established successfully')

    def assertSSLConnection(self, ip, p12):
        self.assertTrue(
            self.connect_ssl(ip, p12),
            'SSL connection established successfully')

    def assertNoSSLConnection(self, ip, p12):
        self.assertFalse(
            self.connect_ssl(ip, p12),
            'SSL connection should not be established')

    @abc.abstractmethod
    def connect_plain(self, ip):
        pass

    @abc.abstractmethod
    def connect_ssl(self, ip, p12):
        pass

    @abc.abstractmethod
    def connect_ssl_client_cert(self, ip, p12):
        pass

    @classmethod
    def _create_secret(cls, p12, password=None):
        if password:
            name = 'p12-container-with-password'
        else:
            name = 'p12-container-passwordless'

        secret = cls.secret_client.create_secret(
            expected_status=201,
            name=cls.get_resource_name(name),
            algorithm='aes', mode='cbc', bit_length=256,
            secret_type='certificate',
            payload=base64.b64encode(p12['p12_payload']),
            payload_content_type="application/octet-stream",
            payload_content_encoding="base64"
        )
        p12['container_ref'] = secret['secret_ref']
        LOG.info('Secret created: %s', p12['container_ref'])

        cls.addClassResourceCleanup(cls.secret_client.delete_secret,
                                    cls.secret_client.ref_to_uuid(
                                        p12['container_ref']))

        if password:
            pw_secret = cls.secret_client.create_secret(
                expected_status=201,
                name=cls.get_resource_name('password-for-p12'),
                secret_type='passphrase',
                payload=password,
                payload_content_type="text/plain",
            )
            p12['password_ref'] = pw_secret['secret_ref']
            LOG.info('Secret for password created: %s', p12['password_ref'])
            cls.addClassResourceCleanup(cls.secret_client.delete_secret,
                                        cls.secret_client.ref_to_uuid(
                                            p12['password_ref']))

        # The resulting dict contains:
        # - key: <plain string private key for certificate>
        # - cert: <plain string certificate contents>
        # - cas: [<single-item array with ca plain string>]
        # - p12_payload: <binary data for p12 container>
        # - container_ref: <secret ref to p12 container in barbican>
        # - password_ref: <secret ref to password in barbican, if present>
        return p12

    def _get_consumers(cls, container_ref):
        secret_uuid = cls.secret_client.ref_to_uuid(container_ref)
        resp = cls.consumer_client.list_consumers_in_secret(
            secret_uuid,
            expected_status=200
        )
        return resp.get('consumers', resp)

    def _find_consumers(cls, consumers, resource_type, resource_id):
        resource_id = str(resource_id)
        return [
            c for c in consumers
            if c.get('resource_type') == resource_type
            if str(c.get('resource_id')) == resource_id
        ]

    def assertConsumer(cls, container_ref, resource_type, resource_id):
        consumers = cls._get_consumers(container_ref)
        matches = cls._find_consumers(consumers, resource_type, resource_id)
        cls.assertTrue(
            matches,
            (f"Consumer not found: type={resource_type}, "
             f"id={resource_id}, actual={consumers}")
        )

    def assertNoConsumer(cls, container_ref, resource_type, resource_id):
        consumers = cls._get_consumers(container_ref)
        matches = cls._find_consumers(consumers, resource_type, resource_id)
        cls.assertFalse(
            matches,
            (f"Unexpected consumer found: type={resource_type}, "
             f"id={resource_id}, actual={consumers}")
        )

    @classmethod
    def resource_setup(cls):
        super(TestInstanceSSLBase, cls).resource_setup()

        cls.secret_client = cls.os_primary.secret_v1.SecretClient()
        cls.consumer_client = cls.os_primary.secret_v1_1.SecretConsumerClient()

        cls.p12 = cls._create_secret(utils.generate_p12(
            cls.instance_ip, client_name=constants.DB_USER))
        cls.p12_with_pass = cls._create_secret(
            utils.generate_p12(
                cls.instance_ip, constants.DB_PASS,
                client_name=constants.DB_USER),
            constants.DB_PASS)

    @decorators.idempotent_id("f2dfb7ec-2898-4fa1-b6e2-9d7d56d98ef4")
    def test_ssl_basic(self):
        LOG.info('Test setting ssl certificate')
        request = {'ssl': {
            'enable': True,
            'container_ref': self.p12['container_ref']}}
        response = self.client.create_resource(
            f"instances/{self.instance_id}/ssl",
            request, expected_status_code=200)
        if response['ssl']['restart_required']:
            LOG.info(f"Restarting instance {self.instance_id}")
            self.restart_instance(self.instance_id)

        self.assertConsumer(
            self.p12['container_ref'], 'instance', self.instance_id)

        LOG.info('Checking current ssl status')
        ssl_info = self.client.get_resource(
            "instances", "%s/ssl" % self.instance_id)
        self.assertEqual('on', ssl_info['ssl']['status'])

        self.assertSSLConnection(self.instance_ip, self.p12)
        LOG.info('Test that attempt to connect with wrong CA should fail')
        self.assertNoSSLConnection(self.instance_ip, self.p12_with_pass)

        LOG.info('Test that password-protected p12 container raises Exception'
                 'if password for pkcs12 container was not provided')
        request = {'ssl': {
            'enable': True,
            'container_ref': self.p12_with_pass['container_ref']}}
        self.assertRaises(exceptions.TempestException,
                          self.client.create_resource,
                          f"instances/{self.instance_id}/ssl", request)

        self.assertConsumer(
            self.p12['container_ref'], 'instance', self.instance_id)
        self.assertNoConsumer(
            self.p12_with_pass['container_ref'],
            'instance', self.instance_id)

        LOG.info('Test new certificate set (renew)')
        request = {'ssl': {
            'enable': True,
            'container_ref': self.p12_with_pass['container_ref'],
            'password_ref': self.p12_with_pass['password_ref']}}
        response = self.client.create_resource(
            f"instances/{self.instance_id}/ssl",
            request, expected_status_code=200)
        if response['ssl']['restart_required']:
            LOG.info(f"Restarting instance {self.instance_id}")
            self.restart_instance(self.instance_id)

        self.assertNoConsumer(
            self.p12['container_ref'], 'instance', self.instance_id)
        self.assertConsumer(
            self.p12_with_pass['container_ref'],
            'instance', self.instance_id)

        ssl_info = self.client.get_resource(
            "instances", "%s/ssl" % self.instance_id)
        self.assertEqual('on', ssl_info['ssl']['status'])
        self.assertSSLConnection(self.instance_ip, self.p12_with_pass)
        LOG.info('Try to connect with old certificate should fail')
        self.assertNoSSLConnection(self.instance_ip, self.p12)

        LOG.info('Test disable ssl')
        request = {'ssl': {'disable': True}}
        try:
            # For some datastores, disabling SSL is forbidden
            response = self.client.create_resource(
                f"instances/{self.instance_id}/ssl",
                request, expected_status_code=200)

            if response['ssl']['restart_required']:
                LOG.info(f"Restarting instance {self.instance_id}")
                self.restart_instance(self.instance_id)

            self.assertNoConsumer(
                self.p12['container_ref'], 'instance', self.instance_id)
            self.assertNoConsumer(
                self.p12_with_pass['container_ref'],
                'instance', self.instance_id)

            ssl_info = self.client.get_resource(
                "instances", "%s/ssl" % self.instance_id)
            self.assertEqual('off', ssl_info['ssl']['status'])

            self.assertPlainConnection(self.instance_ip)
            self.assertNoSSLConnection(self.instance_ip, self.p12)
            self.assertNoSSLConnection(self.instance_ip, self.p12_with_pass)
        except Exception as e:
            if "Not supported" in str(e):
                LOG.info("SSL disable not tested: %s", e)
                pass
            else:
                raise e

    @decorators.idempotent_id("eb578e38-79c6-461d-a0f5-5514265114fc")
    def test_ssl_enforced(self):
        LOG.info("Enable enforced SSL")

        request = {
            'ssl': {
                'enable': True,
                'container_ref': self.p12['container_ref'],
                'mode': 'enforced'
            }
        }

        response = self.client.create_resource(
            f"instances/{self.instance_id}/ssl",
            request,
            expected_status_code=200
        )

        if response['ssl']['restart_required']:
            self.restart_instance(self.instance_id)

        ssl_info = self.client.get_resource(
            "instances", f"{self.instance_id}/ssl")

        self.assertEqual('enforced', ssl_info['ssl']['mode'])

        LOG.info("Plain connection must fail")
        self.assertFalse(self.connect_plain(self.instance_ip))

        LOG.info("SSL must work")
        self.assertSSLConnection(self.instance_ip, self.p12)

    @decorators.idempotent_id("76a4bf3e-28fe-4ce4-acfc-6f5f827ad51d")
    def test_ssl_mtls(self):
        LOG.info("Enable mTLS")

        request = {
            'ssl': {
                'enable': True,
                'container_ref': self.p12['container_ref'],
                'mode': 'mtls'
            }
        }

        response = self.client.create_resource(
            f"instances/{self.instance_id}/ssl",
            request,
            expected_status_code=200
        )

        if response['ssl']['restart_required']:
            self.restart_instance(self.instance_id)

        ssl_info = self.client.get_resource(
            "instances", f"{self.instance_id}/ssl")

        self.assertEqual('mtls', ssl_info['ssl']['mode'])

        LOG.info("Plain must fail")
        self.assertFalse(self.connect_plain(self.instance_ip))

        LOG.info("Password auth over SSL must fail")
        self.assertFalse(self.connect_ssl(self.instance_ip, self.p12))

        LOG.info("Client certificate must work")
        self.assertTrue(
            self.connect_ssl_client_cert(self.instance_ip, self.p12)
        )

    @decorators.idempotent_id("a2bb0122-b6ff-4dbd-8aee-51497892110f")
    def test_ssl_rollback(self):
        LOG.info('Test rolling back SSL certificate')
        request = {
            'ssl': {
                'enable': True,
                'container_ref': self.p12['container_ref']
            }
        }
        response = self.client.create_resource(
            f"instances/{self.instance_id}/ssl",
            request, expected_status_code=200)
        if response['ssl']['restart_required']:
            LOG.info(f"Restarting instance {self.instance_id}")
            self.restart_instance(self.instance_id)

        # Set new certificate before rolling back
        request = {
            'ssl': {
                'enable': True,
                'container_ref': self.p12_with_pass['container_ref'],
                'password_ref': self.p12_with_pass['password_ref'],
                'mode': 'enforced'
            }
        }

        response = self.client.create_resource(
            f"instances/{self.instance_id}/ssl",
            request, expected_status_code=200
        )

        if response['ssl']['restart_required']:
            self.restart_instance(self.instance_id)

        # Rollback to the previous config
        response = self.client.create_resource(
            f"instances/{self.instance_id}/ssl",
            {'ssl': {'rollback': True}},
            expected_status_code=200
        )
        if response['ssl']['restart_required']:
            self.restart_instance(self.instance_id)

        ssl_info = self.client.get_resource(
            "instances", "%s/ssl" % self.instance_id)

        # Configuration should be rolled back to "basic"
        self.assertEqual('basic', ssl_info['ssl']['mode'])

        # Check that the first certificate works
        self.assertSSLConnection(self.instance_ip, self.p12)
        LOG.info('Test that attempt to connect with wrong CA should fail')
        # And the second doesn't work
        self.assertNoSSLConnection(self.instance_ip, self.p12_with_pass)

        # Rolling back again without previous state should raise error
        self.assertRaises(exceptions.TempestException,
                          self.client.create_resource,
                          f"instances/{self.instance_id}/ssl/rollback", {})

    @testtools.skipUnless(CONF.database.rebuild_image_id,
                          'Image for rebuild not configured.')
    @decorators.idempotent_id("40678203-a093-4979-abf7-dff15ce048bd")
    def test_ssl_rebuild(self):
        request = {
            'ssl': {
                'enable': True,
                'container_ref': self.p12['container_ref'],
                'mode': 'enforced'
            }
        }
        response = self.client.create_resource(
            f"instances/{self.instance_id}/ssl",
            request, expected_status_code=200)
        if response['ssl']['restart_required']:
            LOG.info(f"Restarting instance {self.instance_id}")
            self.restart_instance(self.instance_id)

        LOG.info(f"Rebuilding instance {self.instance_id} with image "
                 f"{CONF.database.rebuild_image_id}")
        self.rebuild_instance(self.instance_id, CONF.database.rebuild_image_id)

        ssl_info = self.client.get_resource(
            "instances", "%s/ssl" % self.instance_id)

        # SSL configuration should persist
        self.assertEqual('enforced', ssl_info['ssl']['mode'])

        # Check that the SSL connection really works
        self.assertSSLConnection(self.instance_ip, self.p12)

    @testtools.skipUnless(CONF.database.run_full_tests,
                          "renew SSL replication tests are disabled")
    @decorators.idempotent_id("3c9e6f5d-3998-4cf0-822a-2d8762f9981d")
    def test_ssl_replication_renew(self):
        LOG.info(f"Creating replica for instance {self.instance_id}")
        name = self.get_resource_name("replica")
        replica = self.create_instance(name, replica_of=self.instance_id,
                                       create_user=self.create_user)
        replica_id = replica['id']
        self.addCleanup(self.wait_for_instance_status, replica_id,
                        need_delete=True, expected_status='DELETED')
        self.wait_for_instance_status(
            replica_id,
            expected_op_status=["HEALTHY"],
            timeout=CONF.database.database_build_timeout * 2)
        replica = self.client.get_resource(
            "instances", replica_id)['instance']
        replica_ip = self.get_instance_ip(replica)

        LOG.info('Test that ssl certificate set for replica is disabled')
        request = {'ssl': {
            'enable': True,
            'mode': 'basic',
            'container_ref': self.p12['container_ref']}}
        self.assertRaises(exceptions.TempestException,
                          self.client.create_resource,
                          f"instances/{replica_id}/ssl", request)

        LOG.info('Test setting ssl certificate for replication')
        request = {'ssl': {
            'enable': True,
            'mode': 'basic',
            'container_ref': self.p12['container_ref']}}
        response = self.client.create_resource(
            f"instances/{self.instance_id}/ssl",
            request, expected_status_code=200)
        if response['ssl']['restart_required']:
            LOG.info(f"Restarting instance {self.instance_id}")
            self.restart_instance(self.instance_id)
            LOG.info(f"Restarting instance {replica_id}")
            self.restart_instance(replica_id)

        self.assertSSLConnection(self.instance_ip, self.p12)
        self.assertSSLConnection(replica_ip, self.p12)

        LOG.info('Test setting new ssl certificate for replication')
        request = {'ssl': {
            'enable': True,
            'mode': 'basic',
            'container_ref': self.p12_with_pass['container_ref'],
            'password_ref': self.p12_with_pass['password_ref']}}
        response = self.client.create_resource(
            f"instances/{self.instance_id}/ssl",
            request, expected_status_code=200)
        if response['ssl']['restart_required']:
            LOG.info(f"Restarting instance {self.instance_id}")
            self.restart_instance(self.instance_id)
            LOG.info(f"Restarting instance {replica_id}")
            self.restart_instance(replica_id)
        self.assertSSLConnection(self.instance_ip, self.p12_with_pass)
        self.assertSSLConnection(replica_ip, self.p12_with_pass)
        # check that plain text mode is available
        self.assertNoSSLConnection(self.instance_ip, self.p12)
        self.assertNoSSLConnection(replica_ip, self.p12)

    @decorators.idempotent_id("266b3c7e-0dfd-4916-9be2-8977bcd6f8ca")
    def test_ssl_replication_basic(self):
        # Test replica attach in basic mode
        request = {'ssl': {
            'enable': True,
            'mode': 'basic',
            'container_ref': self.p12['container_ref']}}
        response = self.client.create_resource(
            f"instances/{self.instance_id}/ssl",
            request, expected_status_code=200)
        if response['ssl']['restart_required']:
            LOG.info(f"Restarting instance {self.instance_id}")
            self.restart_instance(self.instance_id)

        LOG.info('Test attached replica has proper ssl cert [basic]')
        name = self.get_resource_name("replica-test-basic")
        replica = self.create_instance(name, replica_of=self.instance_id,
                                       create_user=self.create_user)
        replica_id = replica['id']
        self.addCleanup(self.wait_for_instance_status, replica_id,
                        need_delete=True, expected_status='DELETED')
        self.wait_for_instance_status(
            replica_id,
            expected_op_status=["HEALTHY"],
            timeout=CONF.database.database_build_timeout * 2)
        replica = self.client.get_resource(
            "instances", replica_id)['instance']
        replica_ip = self.get_instance_ip(replica)

        LOG.info('Checking ssl status on replica')
        ssl_info = self.client.get_resource(
            "instances", "%s/ssl" % replica_id)
        LOG.info('Replica ssl status: %s', ssl_info['ssl'])
        self.assertEqual(ssl_info['ssl']['status'], 'on')
        self.assertEqual(ssl_info['ssl']['mode'], 'basic')
        self.assertSSLConnection(self.instance_ip, self.p12)
        self.assertSSLConnection(replica_ip, self.p12)

        # Check consumers
        self.assertConsumer(
            self.p12['container_ref'], 'instance', self.instance_id)
        self.assertConsumer(
            self.p12['container_ref'], 'instance', replica_id)

        # Remove instance as client, not admin, this is important
        # because admins can't control barbican secrets, only
        # project members has access rights.
        LOG.info('Remove replica to test consumer cleanup')
        self.client.delete_resource('instances', replica_id)
        self.wait_for_instance_status(
            replica_id,
            expected_op_status=["DELETED"],
            need_delete=True,
            timeout=CONF.database.database_build_timeout * 2)

        self.assertNoConsumer(
            self.p12['container_ref'], 'instance', replica_id)

    @testtools.skipUnless(CONF.database.run_full_tests,
                          "enforced SSL replication tests are disabled")
    @decorators.idempotent_id("cf446e27-90fc-437d-8ad8-7d622e94660b")
    def test_ssl_replication_enforced(self):
        # Test replica attach in enforced mode
        LOG.info('Test setting ssl certificate for replication [enforced]')
        request = {'ssl': {
            'enable': True,
            'mode': 'enforced',
            'container_ref': self.p12['container_ref']}}
        response = self.client.create_resource(
            f"instances/{self.instance_id}/ssl",
            request, expected_status_code=200)
        if response['ssl']['restart_required']:
            LOG.info(f"Restarting instance {self.instance_id}")
            self.restart_instance(self.instance_id)

        LOG.info('Test attached replica has proper ssl cert [enforced]')
        name = self.get_resource_name("replica-test-enforced")
        replica = self.create_instance(name, replica_of=self.instance_id,
                                       create_user=self.create_user)
        replica_id = replica['id']
        self.addCleanup(self.wait_for_instance_status, replica_id,
                        need_delete=True, expected_status='DELETED')
        self.wait_for_instance_status(
            replica_id,
            expected_op_status=["HEALTHY"],
            timeout=CONF.database.database_build_timeout * 2)
        replica = self.client.get_resource(
            "instances", replica_id)['instance']
        replica_ip = self.get_instance_ip(replica)

        LOG.info('Checking ssl status on replica')
        ssl_info = self.client.get_resource(
            "instances", "%s/ssl" % replica_id)
        LOG.info('Replica ssl status: %s', ssl_info['ssl'])
        self.assertEqual(ssl_info['ssl']['status'], 'on')
        self.assertEqual(ssl_info['ssl']['mode'], 'enforced')
        self.assertSSLConnection(replica_ip, self.p12)

        LOG.info("Plain connection must fail")
        self.assertFalse(self.connect_plain(replica_ip))

    @testtools.skipUnless(CONF.database.run_full_tests,
                          "mTLS replication tests are disabled")
    @decorators.idempotent_id("2f42a56e-70f6-4387-9337-4c4bd2c6e7ab")
    def test_ssl_replication_mtls(self):
        # Test replica attach in mTLS mode
        LOG.info('Test setting ssl certificate for replication [mtls]')
        request = {'ssl': {
            'enable': True,
            'mode': 'mtls',
            'container_ref': self.p12['container_ref']}}
        response = self.client.create_resource(
            f"instances/{self.instance_id}/ssl",
            request, expected_status_code=200)
        if response['ssl']['restart_required']:
            LOG.info(f"Restarting instance {self.instance_id}")
            self.restart_instance(self.instance_id)

        LOG.info('Test attached replica has proper ssl cert [mtls]')
        name = self.get_resource_name("replica-test-mtls")
        replica = self.create_instance(name, replica_of=self.instance_id,
                                       create_user=self.create_user)
        replica_id = replica['id']
        self.addCleanup(self.wait_for_instance_status, replica_id,
                        need_delete=True, expected_status='DELETED')
        self.wait_for_instance_status(
            replica_id,
            expected_op_status=["HEALTHY"],
            timeout=CONF.database.database_build_timeout * 2)
        replica = self.client.get_resource(
            "instances", replica_id)['instance']
        replica_ip = self.get_instance_ip(replica)

        LOG.info('Checking ssl status on replica')
        ssl_info = self.client.get_resource(
            "instances", "%s/ssl" % replica_id)
        LOG.info('Replica ssl status: %s', ssl_info['ssl'])
        self.assertEqual(ssl_info['ssl']['status'], 'on')
        self.assertEqual(ssl_info['ssl']['mode'], 'mtls')

        self.assertTrue(
            self.connect_ssl_client_cert(self.instance_ip, self.p12)
        )
        # At this point, server certificate contains only master
        # ip address in CN/SAN, so attempt to connect should fail
        self.assertFalse(
            self.connect_ssl_client_cert(replica_ip, self.p12)
        )
        LOG.info("Plain connection must fail")
        self.assertFalse(self.connect_plain(replica_ip))

        # Create new certificate with multi-ip SAN
        replication_p12 = self._create_secret(utils.generate_p12(
            [self.instance_ip, replica_ip],
            client_name=constants.DB_USER))
        request = {'ssl': {
            'enable': True,
            'mode': 'mtls',
            'container_ref': replication_p12['container_ref']}}
        response = self.client.create_resource(
            f"instances/{self.instance_id}/ssl",
            request, expected_status_code=200)
        if response['ssl']['restart_required']:
            LOG.info(f"Restarting instance {self.instance_id}")
            self.restart_instance(self.instance_id)
            LOG.info(f"Restarting instance {replica_id}")
            self.restart_instance(replica_id)
        self.assertTrue(
            self.connect_ssl_client_cert(self.instance_ip, replication_p12)
        )
        self.assertTrue(
            self.connect_ssl_client_cert(replica_ip, replication_p12)
        )


class TestInstanceSSLMySQLBase(TestInstanceSSLBase):
    def connect_plain(self, ip):
        db_url = (
            f"mysql+pymysql://{constants.DB_USER}:{constants.DB_PASS}"
            f"@{ip}:3306/{constants.DB_NAME}"
            f"?ssl_disabled=true"
        )

        try:
            with utils.SQLClient(db_url) as db_client:
                db_client.mysql_execute("SELECT 1;")
            return True
        except Exception:
            return False

    def connect_ssl(self, ip, p12):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(p12['cas'][0])
            ca_cert_path = f.name

        db_url = (
            f"mysql+pymysql://{constants.DB_USER}:{constants.DB_PASS}"
            f"@{ip}:3306/{constants.DB_NAME}"
        )
        connect_args = {
            "ssl": {
                "ca": ca_cert_path,
                "cert_reqs": ssl.CERT_REQUIRED,
                "check_hostname": False
            }
        }
        try:
            with utils.SQLClient(
                    db_url, connect_args=connect_args) as db_client:
                db_client.mysql_execute("SELECT 1;")
                result = db_client.mysql_execute(
                    "SHOW SESSION STATUS LIKE 'Ssl_cipher';"
                )
                row = result.fetchone()
            return bool(row and row[1])
        except Exception as e:
            LOG.info(
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

        try:
            conn = pymysql.connect(
                host=ip,
                user=constants.DB_USER,
                # MySQL and MariaDB still require password in addition to
                # X509 certificate verification.
                password=constants.DB_PASS,
                database=constants.DB_NAME,
                ssl={
                    "ca": ca_path,
                    "cert": cert_path,
                    "key": key_path,
                }
            )
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except Exception as e:
            LOG.warning(
                'Exception during SSL check: %s', e, exc_info=CONF.debug)
            return False
        finally:
            for path in [ca_path, cert_path, key_path]:
                if os.path.exists(path):
                    os.remove(path)
