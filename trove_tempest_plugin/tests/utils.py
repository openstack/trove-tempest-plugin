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
import ipaddress
import time

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography import x509
from cryptography.x509.oid import NameOID
from datetime import datetime
from datetime import timedelta

from oslo_log import log as logging
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sqlalchemy
from sqlalchemy import text
from tempest.lib import exceptions

LOG = logging.getLogger(__name__)


def wait_for_removal(delete_func, show_func, *args, **kwargs):
    """Call the delete function, then wait for it to be 'NotFound'

    :param delete_func: The delete function to call.
    :param show_func: The show function to call looking for 'NotFound'.
    :param ID: The ID of the object to delete/show.
    :raises TimeoutException: The object did not achieve the status or ERROR in
                              the check_timeout period.
    :returns: None
    """
    check_timeout = 15
    try:
        delete_func(*args, **kwargs)
    except exceptions.NotFound:
        return

    start = int(time.time())
    LOG.info('Waiting for object to be NotFound')
    while True:
        try:
            show_func(*args, **kwargs)
        except exceptions.NotFound:
            return

        if int(time.time()) - start >= check_timeout:
            message = ('%s did not raise NotFound in %s seconds.' %
                       (show_func.__name__, check_timeout))
            raise exceptions.TimeoutException(message)
        time.sleep(3)


def init_engine(db_url, connect_args={}):
    return sqlalchemy.create_engine(db_url, connect_args=connect_args)


class SQLClient(object):
    def __init__(self, conn_str, connect_args={}):
        self.engine = init_engine(conn_str, connect_args=connect_args)

    def conn_execute(self, conn, cmds):
        if isinstance(cmds, str):
            result = conn.execute(text(cmds))
            return result

        for cmd in cmds:
            conn.execute(text(cmd))

    def pgsql_execute(self, cmds, **kwargs):
        try:
            with self.engine.connect() as conn:
                conn.connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
                return self.conn_execute(conn, cmds)
        except Exception as e:
            raise exceptions.TempestException(
                'Failed to execute database command %s, error: %s' %
                (cmds, str(e))
            )

    def mysql_execute(self, cmds, **kwargs):
        try:
            with self.engine.begin() as conn:
                return self.conn_execute(conn, cmds)
        except Exception as e:
            raise exceptions.TempestException(
                'Failed to execute database command %s, error: %s' %
                (cmds, str(e))
            )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.engine.dispose()


# Generate self-signed PKCS12 container with a private key, ca and certificate
# signed by ca. May be password-protected if p12_pass is provided.
def generate_p12(cn, p12_pass=None, client_name="client"):
    # Generate CA key
    ca_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    ca_subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "Trove Test CA"),
    ])

    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_subject)
        .issuer_name(ca_subject)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow())
        .not_valid_after(datetime.utcnow() + timedelta(days=365))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )

    # Generate server key
    server_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    if isinstance(cn, list):
        ips = cn
        cn = 'Multi ip cert'
    else:
        ips = [cn]

    server_subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, cn),
    ])

    san_list = [x509.IPAddress(ipaddress.ip_address(ip)) for ip in ips]

    server_cert = (
        x509.CertificateBuilder()
        .subject_name(server_subject)
        .issuer_name(ca_cert.subject)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow())
        .not_valid_after(datetime.utcnow() + timedelta(days=365))
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        .add_extension(
            x509.SubjectAlternativeName(san_list),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )

    # Choose encryption algorithm
    if p12_pass:
        encryption = serialization.BestAvailableEncryption(
            p12_pass.encode()
        )
    else:
        encryption = serialization.NoEncryption()

    # Serialize server private key (PEM, unencrypted)
    key_pem = server_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    # Serialize server certificate (PEM)
    cert_pem = server_cert.public_bytes(
        encoding=serialization.Encoding.PEM,
    ).decode("utf-8")

    # Serialize CA certificate (PEM)
    ca_pem = ca_cert.public_bytes(
        encoding=serialization.Encoding.PEM,
    ).decode("utf-8")

    # Create PKCS#12 payload
    p12_payload = pkcs12.serialize_key_and_certificates(
        name=b"server",
        key=server_key,
        cert=server_cert,
        cas=[ca_cert],
        encryption_algorithm=encryption,
    )

    client_key_pem, client_cert_pem = generate_client_cert(
        ca_key, ca_cert, client_name=client_name)

    return {
        "key": key_pem,
        "cert": cert_pem,
        "cas": [ca_pem],
        "p12_payload": p12_payload,
        "client_key": client_key_pem,
        "client_cert": client_cert_pem
    }


def generate_client_cert(ca_key, ca_cert, client_name="client"):
    client_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, client_name),
    ])

    client_cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(client_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow())
        .not_valid_after(datetime.utcnow() + timedelta(days=365))
        .sign(ca_key, hashes.SHA256())
    )

    client_key_pem = client_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    client_cert_pem = client_cert.public_bytes(
        encoding=serialization.Encoding.PEM,
    ).decode("utf-8")

    return client_key_pem, client_cert_pem
