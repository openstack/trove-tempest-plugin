# Copyright 2014 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
import time

from oslo_log import log as logging
from oslo_service import loopingcall
from oslo_utils import netutils
from oslo_utils import uuidutils
from swiftclient import client as swift_client
from tempest import config
from tempest.lib.common.utils import data_utils
from tempest.lib.common.utils import test_utils
from tempest.lib import exceptions
from tempest import test
import tenacity

from trove_tempest_plugin.tests import constants
from trove_tempest_plugin.tests import exceptions as trove_exc
from trove_tempest_plugin.tests import utils

CONF = config.CONF
LOG = logging.getLogger(__name__)


class BaseTroveTest(test.BaseTestCase):
    credentials = ('admin', 'primary')
    datastore = None
    instance = None
    instance_id = None
    instance_ip = None
    password = ""
    create_user = True
    enable_root = False

    @classmethod
    def get_resource_name(cls, resource_type):
        prefix = "trove-tempest-%s" % cls.__name__
        return data_utils.rand_name(resource_type, prefix=prefix)

    @classmethod
    def skip_checks(cls):
        super(BaseTroveTest, cls).skip_checks()

        if not CONF.service_available.trove:
            raise cls.skipException("Database service is not available.")

        if cls.datastore not in CONF.database.enabled_datastores:
            raise cls.skipException(
                "Datastore %s is not enabled." % cls.datastore
            )

    @classmethod
    def get_swift_client(cls):
        auth_version = "3.0"
        auth_url = CONF.identity.uri_v3
        user = cls.os_primary.credentials.username
        key = cls.os_primary.credentials.password
        tenant_name = cls.os_primary.credentials.project_name
        region_name = cls.os_primary.region
        os_options = {'tenant_name': tenant_name, 'region_name': region_name}

        return swift_client.Connection(
            auth_url, user, key, auth_version=auth_version,
            os_options=os_options)

    @classmethod
    def get_swift_admin_client(cls):
        auth_version = "3.0"
        auth_url = CONF.identity.uri_v3
        user = cls.os_admin.credentials.username
        key = cls.os_admin.credentials.password
        tenant_name = cls.os_admin.credentials.project_name
        region_name = cls.os_admin.region
        os_options = {'tenant_name': tenant_name, 'region_name': region_name}

        return swift_client.Connection(
            auth_url, user, key, auth_version=auth_version,
            os_options=os_options)

    @classmethod
    def setup_clients(cls):
        super(BaseTroveTest, cls).setup_clients()

        cls.client = cls.os_primary.database.TroveClient()
        cls.admin_client = cls.os_admin.database.TroveClient()
        cls.admin_server_client = cls.os_admin.servers_client
        cls.account_client = cls.os_primary.account_client
        cls.container_client = cls.os_primary.container_client
        cls.object_client = cls.os_primary.object_client
        cls.admin_container_client = cls.os_admin.container_client
        cls.admin_object_client = cls.os_admin.object_client
        # Swift client is special, we want to re-use the log_generator func
        # in python-troveclient.
        cls.swift = cls.get_swift_client()
        cls.swift_admin = cls.get_swift_admin_client()

    @classmethod
    def setup_credentials(cls):
        # Do not create network resources automatically.
        cls.set_network_resources()
        super(BaseTroveTest, cls).setup_credentials()

    @classmethod
    @tenacity.retry(
        retry=tenacity.retry_if_exception_type(exceptions.Conflict),
        wait=tenacity.wait_incrementing(1, 1, 5),
        stop=tenacity.stop_after_attempt(15)
    )
    def _delete_network(cls, net_id):
        """Make sure the network is deleted.

        Neutron can be slow to clean up ports from the subnets/networks.
        Retry this delete a few times if we get a "Conflict" error to give
        neutron time to fully cleanup the ports.
        """
        networks_client = cls.os_primary.networks_client
        try:
            networks_client.delete_network(net_id)
        except Exception:
            LOG.error('Unable to delete network %s', net_id)
            raise

    @classmethod
    @tenacity.retry(
        retry=tenacity.retry_if_exception_type(exceptions.Conflict),
        wait=tenacity.wait_incrementing(1, 1, 5),
        stop=tenacity.stop_after_attempt(15)
    )
    def _delete_subnet(cls, subnet_id):
        """Make sure the subnet is deleted.

        Neutron can be slow to clean up ports from the subnets/networks.
        Retry this delete a few times if we get a "Conflict" error to give
        neutron time to fully cleanup the ports.
        """
        subnets_client = cls.os_primary.subnets_client
        try:
            subnets_client.delete_subnet(subnet_id)
        except Exception:
            LOG.error('Unable to delete subnet %s', subnet_id)
            raise

    @classmethod
    def _create_network(cls):
        """Create database instance network."""
        networks_client = cls.os_primary.networks_client
        subnets_client = cls.os_primary.subnets_client
        routers_client = cls.os_primary.routers_client

        if CONF.database.shared_network:
            private_network = CONF.database.shared_network
            if not uuidutils.is_uuid_like(private_network):
                networks = networks_client.list_networks()['networks']
                for net in networks:
                    if net['name'] == private_network:
                        private_network = net['id']
                        break
                else:
                    raise exceptions.NotFound(
                        'Shared network %s not found' % private_network
                    )

            cls.private_network = private_network
            return

        network_kwargs = {"name": cls.get_resource_name("network")}
        result = networks_client.create_network(**network_kwargs)
        LOG.info('Private network created: %s', result['network'])
        cls.private_network = result['network']["id"]
        cls.addClassResourceCleanup(
            utils.wait_for_removal,
            cls._delete_network,
            networks_client.show_network,
            cls.private_network
        )

        subnet_kwargs = {
            'name': cls.get_resource_name("subnet"),
            'network_id': cls.private_network,
            'cidr': CONF.database.subnet_cidr,
            'ip_version': 4
        }
        result = subnets_client.create_subnet(**subnet_kwargs)
        subnet_id = result['subnet']['id']
        LOG.info('Private subnet created: %s', result['subnet'])
        cls.addClassResourceCleanup(
            utils.wait_for_removal,
            cls._delete_subnet,
            subnets_client.show_subnet,
            subnet_id
        )

        # In dev node, Trove instance needs to connect with control host
        router_params = {
            'name': cls.get_resource_name("router"),
            'external_gateway_info': {
                "network_id": CONF.network.public_network_id
            }
        }
        result = routers_client.create_router(**router_params)
        router_id = result['router']['id']
        LOG.info('Private router created: %s', result['router'])
        cls.addClassResourceCleanup(
            utils.wait_for_removal,
            routers_client.delete_router,
            routers_client.show_router,
            router_id
        )

        routers_client.add_router_interface(router_id, subnet_id=subnet_id)
        LOG.info('Subnet %s added to the router %s', subnet_id, router_id)
        cls.addClassResourceCleanup(
            routers_client.remove_router_interface,
            router_id,
            subnet_id=subnet_id
        )

    @classmethod
    def resource_setup(cls):
        super(BaseTroveTest, cls).resource_setup()

        # Create network for database instance, use cls.private_network as the
        # network ID.
        cls._create_network()

        instance = cls.create_instance(create_user=cls.create_user)
        cls.instance_id = instance['id']
        cls.wait_for_instance_status(cls.instance_id)
        cls.instance = cls.client.get_resource(
            "instances", cls.instance_id)['instance']
        cls.instance_ip = cls.get_instance_ip(cls.instance)

        if cls.enable_root:
            cls.password = cls.get_root_pass(cls.instance_id)

    def assert_single_item(self, items, **props):
        return self.assert_multiple_items(items, 1, **props)[0]

    def assert_multiple_items(self, items, count, **props):
        """Check if a object is in a list of objects.

        e.g. props is a sub-dict, items is a list of dicts.
        """

        def _matches(item, **props):
            for prop_name, prop_val in props.items():
                v = item[prop_name] if isinstance(
                    item, dict) else getattr(item, prop_name)

                if v != prop_val:
                    return False

            return True

        filtered_items = list(
            [item for item in items if _matches(item, **props)]
        )

        found = len(filtered_items)

        if found != count:
            LOG.info("[FAIL] items=%s, expected_props=%s", str(items), props)
            self.fail("Wrong number of items found [props=%s, "
                      "expected=%s, found=%s]" % (props, count, found))

        return filtered_items

    @classmethod
    def delete_swift_account(cls):
        LOG.info(f"Cleaning up Swift account")
        try:
            cls.account_client.delete('')
        except exceptions.NotFound:
            pass

    @classmethod
    def delete_swift_containers(cls, container_client, object_client,
                                containers):
        """Remove containers and all objects in them.

        The containers should be visible from the container_client given.
        Will not throw any error if the containers don't exist.
        Will not check that object and container deletions succeed.
        After delete all the objects from a container, it will wait 3
        seconds before delete the container itself, in order for deployments
        using HA proxy sync the deletion properly, otherwise, the container
        might fail to be deleted because it's not empty.
        """
        if isinstance(containers, str):
            containers = [containers]

        for cont in containers:
            try:
                params = {'limit': 9999, 'format': 'json'}
                _, objlist = container_client.list_container_objects(
                    cont,
                    params)
                # delete every object in the container
                for obj in objlist:
                    test_utils.call_and_ignore_notfound_exc(
                        object_client.delete_object, cont, obj['name'])

                # sleep 3 seconds to sync the deletion of the objects
                # in HA deployment
                time.sleep(3)

                container_client.delete_container(cont)
            except exceptions.NotFound:
                pass

    @classmethod
    def create_instance(cls, name=None, datastore_version=None,
                        database=constants.DB_NAME, username=constants.DB_USER,
                        password=constants.DB_PASS, backup_id=None,
                        replica_of=None, create_user=True):
        """Create database instance.

        Creating database instance is time-consuming, so we define this method
        as a class method, which means the instance is shared in a single
        TestCase. According to
        https://docs.openstack.org/tempest/latest/write_tests.html#adding-a-new-testcase,
        all test methods within a TestCase are assumed to be executed serially.
        """
        name = name or cls.get_resource_name("instance")

        # Flavor, volume, datastore are not needed for creating replica.
        if replica_of:
            body = {
                "instance": {
                    "name": name,
                    "nics": [{"net-id": cls.private_network}],
                    "access": {"is_public": True},
                    "replica_of": replica_of,
                }
            }

        # Get datastore version. Get from API if the default ds version is not
        # configured.
        elif not datastore_version:
            default_versions = CONF.database.default_datastore_versions
            datastore_version = default_versions.get(cls.datastore)
            if not datastore_version:
                res = cls.client.list_resources("datastores")
                for d in res['datastores']:
                    if d['name'] == cls.datastore:
                        if d.get('default_version'):
                            datastore_version = d['default_version']
                        else:
                            datastore_version = d['versions'][0]['name']
                        break
            if not datastore_version:
                message = ('Failed to get available datastore version.')
                raise exceptions.TempestException(message)

        if not replica_of:
            body = {
                "instance": {
                    "name": name,
                    "datastore": {
                        "type": cls.datastore,
                        "version": datastore_version
                    },
                    "flavorRef": CONF.database.flavor_id,
                    "volume": {
                        "size": 1,
                        "type": CONF.database.volume_type
                    },
                    "nics": [{"net-id": cls.private_network}],
                    "access": {"is_public": True}
                }
            }
            if backup_id:
                body['instance'].update(
                    {'restorePoint': {'backupRef': backup_id}})
            if create_user:
                body['instance'].update({
                    'databases': [{"name": database}],
                    "users": [
                        {
                            "name": username,
                            "password": password,
                            "databases": [{"name": database}]
                        }
                    ]
                })

        res = cls.client.create_resource("instances", body)
        cls.addClassResourceCleanup(cls.wait_for_instance_status,
                                    res["instance"]["id"],
                                    need_delete=True,
                                    expected_status="DELETED")

        return res["instance"]

    @classmethod
    def restart_instance(cls, instance_id):
        """Restart database service and wait until it's healthy."""
        cls.client.create_resource(
            f"instances/{instance_id}/action",
            {"restart": {}},
            expected_status_code=202,
            need_response=False)
        cls.wait_for_instance_status(instance_id)

    @classmethod
    def wait_for_instance_status(cls, id,
                                 expected_status=["HEALTHY", "ACTIVE"],
                                 need_delete=False,
                                 timeout=CONF.database.database_build_timeout):
        def _wait():
            try:
                res = cls.client.get_resource("instances", id)
                cur_status = res["instance"]["status"]
            except exceptions.NotFound:
                if need_delete or "DELETED" in expected_status:
                    LOG.info('Instance %s is deleted', id)
                    raise loopingcall.LoopingCallDone()
                return

            if cur_status in expected_status:
                LOG.info('Instance %s becomes %s', id, cur_status)
                raise loopingcall.LoopingCallDone()
            elif "ERROR" not in expected_status and cur_status == "ERROR":
                # If instance status goes to ERROR but is not expected, stop
                # waiting

                res = cls.admin_client.get_resource("instances", id)
                LOG.info(f'Instance fault msg: {res["instance"].get("fault")}')

                # Show trove-guestagent log for debug purpose.
                # Only admin user is able to publish and show the trove guest
                # agent log. Make sure the container is deleted after fetching
                # the log.
                try:
                    LOG.info(f"Publishing guest log for instance {id}")
                    cls.publish_log(id, 'guest')
                    LOG.info(f"Getting guest log content for instance {id}")
                    log_gen = cls.log_generator(id, 'guest', lines=0)
                    log_content = "".join([chunk for chunk in log_gen()])
                    LOG.info(
                        f"\n=============================================\n"
                        f"Trove guest agent log for instance {id}\n"
                        f"=============================================")
                    LOG.info(log_content)
                except Exception as err:
                    LOG.warning(f"Failed to get guest log for instance {id}, "
                                f"error: {str(err)}")
                finally:
                    # Remove the swift container of database logs.
                    LOG.info(f"Deleting swift container "
                             f"{CONF.database.database_log_container}")
                    cls.delete_swift_containers(
                        cls.admin_container_client, cls.admin_object_client,
                        CONF.database.database_log_container)

                message = "Instance status is ERROR."
                caller = test_utils.find_test_caller()
                if caller:
                    message = '({caller}) {message}'.format(caller=caller,
                                                            message=message)
                raise exceptions.UnexpectedResponseCode(message)

        if type(expected_status) != list:
            expected_status = [expected_status]

        if need_delete:
            # If resource already removed, return
            try:
                cls.client.get_resource("instances", id)
            except exceptions.NotFound:
                LOG.info('Instance %s not found', id)
                return

            LOG.info(f"Deleting instance {id}")
            cls.admin_client.force_delete_instance(id)

        timer = loopingcall.FixedIntervalWithTimeoutLoopingCall(_wait)
        try:
            timer.start(interval=10, timeout=timeout, initial_delay=5).wait()
        except loopingcall.LoopingCallTimeOut:
            message = ("Instance %s is not in the expected status: %s" %
                       (id, expected_status))
            caller = test_utils.find_test_caller()
            if caller:
                message = '({caller}) {message}'.format(caller=caller,
                                                        message=message)
            raise exceptions.TimeoutException(message)

    @classmethod
    def get_instance_ip(cls, instance=None):
        if not instance:
            instance = cls.client.get_resource(
                "instances", cls.instance_id)['instance']

        # TODO(lxkong): IPv6 needs to be tested.
        v4_ip = None

        if 'addresses' in instance:
            for addr_info in instance['addresses']:
                if addr_info['type'] == 'private':
                    v4_ip = addr_info['address']
                if addr_info['type'] == 'public':
                    v4_ip = addr_info['address']
                    break
        else:
            ips = instance.get('ip', [])
            for ip in ips:
                if netutils.is_valid_ipv4(ip):
                    v4_ip = ip

        if not v4_ip:
            message = ('Failed to get instance IP address.')
            raise exceptions.TempestException(message)

        return v4_ip

    def get_databases(self, instance_id, **kwargs):
        url = f'instances/{instance_id}/databases'
        ret = self.client.list_resources(url)
        return ret['databases']

    def get_users(self, instance_id):
        url = f'instances/{instance_id}/users'
        ret = self.client.list_resources(url)
        return ret['users']

    @classmethod
    def create_backup(cls, instance_id, backup_name, incremental=False,
                      parent_id=None, description=None):
        body = {
            "backup": {
                "name": backup_name,
                "instance": instance_id,
                "incremental": 1 if incremental else 0,
            }
        }
        if description:
            body['backup']['description'] = description
        if parent_id:
            body['backup']['parent_id'] = parent_id

        res = cls.client.create_resource("backups", body,
                                         expected_status_code=202)
        cls.addClassResourceCleanup(cls.wait_for_backup_status,
                                    res["backup"]['id'],
                                    expected_status='',
                                    need_delete=True)
        return res["backup"]

    @classmethod
    def delete_backup(cls, backup_id, ignore_notfound=False):
        cls.client.delete_resource('backups', backup_id,
                                   ignore_notfound=ignore_notfound)

    @classmethod
    def wait_for_backup_status(cls, id, expected_status=["COMPLETED"],
                               need_delete=False):
        def _wait():
            try:
                res = cls.client.get_resource("backups", id)
                cur_status = res["backup"]["status"]
            except exceptions.NotFound:
                if need_delete or "DELETED" in expected_status:
                    LOG.info('Backup %s is deleted', id)
                    raise loopingcall.LoopingCallDone()
                return

            if cur_status in expected_status:
                LOG.info('Backup %s becomes %s', id, cur_status)
                raise loopingcall.LoopingCallDone()
            elif "FAILED" not in expected_status and cur_status == "FAILED":
                # If backup status goes to FAILED but is not expected, stop
                # waiting
                message = "Backup status is FAILED."
                caller = test_utils.find_test_caller()
                if caller:
                    message = '({caller}) {message}'.format(caller=caller,
                                                            message=message)
                raise exceptions.UnexpectedResponseCode(message)

        if type(expected_status) != list:
            expected_status = [expected_status]

        if need_delete:
            # If resource already removed, return
            try:
                cls.client.get_resource("backups", id)
            except exceptions.NotFound:
                LOG.info('Backup %s not found', id)
                return

            LOG.info(f"Deleting backup {id}")
            cls.delete_backup(id, ignore_notfound=True)

        timer = loopingcall.FixedIntervalWithTimeoutLoopingCall(_wait)
        try:
            timer.start(interval=10,
                        timeout=CONF.database.backup_wait_timeout).wait()
        except loopingcall.LoopingCallTimeOut:
            message = ("Backup %s is not in the expected status: %s" %
                       (id, expected_status))
            caller = test_utils.find_test_caller()
            if caller:
                message = '({caller}) {message}'.format(caller=caller,
                                                        message=message)
            raise exceptions.TimeoutException(message)

    @classmethod
    def get_root_pass(cls, instance_id):
        resp = cls.client.create_resource(f"instances/{instance_id}/root", {})
        return resp['user']['password']

    @classmethod
    def rebuild_instance(cls, instance_id, image_id):
        rebuild_req = {
            "rebuild": {
                "image_id": image_id
            }
        }
        cls.admin_client.create_resource(
            f"mgmt/instances/{instance_id}/action",
            rebuild_req, expected_status_code=202,
            need_response=False)
        cls.wait_for_instance_status(instance_id)

    @classmethod
    def create_config(cls, name, values, datastore, datastore_version):
        create_config = {
            "configuration": {
                "datastore": {
                    "type": datastore,
                    "version": datastore_version
                },
                "values": values,
                "name": name
            }
        }
        config = cls.client.create_resource('configurations', create_config)
        return config

    @classmethod
    def attach_config(cls, instance_id, config_id):
        attach_config = {
            "instance": {
                "configuration": config_id
            }
        }
        cls.client.put_resource(f'instances/{instance_id}', attach_config)

    @classmethod
    def detach_config(cls, instance_id):
        detach_config = {
            "instance": {
                "configuration": None
            }
        }
        cls.client.put_resource(f'instances/{instance_id}', detach_config)

    @classmethod
    def publish_log(cls, instance_id, name='guest'):
        client = cls.admin_client if name == 'guest' else cls.client
        req_body = {
            'name': name,
            'publish': 1
        }
        client.create_resource(f"instances/{instance_id}/log",
                               req_body)

    @classmethod
    def get_log_info(cls, instance_id, name='guest'):
        req_body = {
            'name': name,
        }
        return cls.admin_client.create_resource(
            f"instances/{instance_id}/log",
            req_body)

    @classmethod
    def _get_container_info(cls, instance_id, log_name):
        try:
            log_info = cls.get_log_info(instance_id, log_name)['log']
            container = log_info['container']
            prefix = log_info['prefix']
            metadata_file = log_info['metafile']
            return container, prefix, metadata_file
        except swift_client.ClientException as ex:
            if ex.http_status == 404:
                raise trove_exc.GuestLogNotFound()
            raise trove_exc.TroveTempestException()

    @classmethod
    def log_generator(cls, instance_id, log_name, lines=50):
        """Return generator to yield the last <lines> lines of guest log.

        This method is copied from python-troveclient.
        """
        swift_cli = cls.swift_admin if log_name == 'guest' else cls.swift

        def _log_generator(instance_id, log_name, lines):
            try:
                container, prefix, metadata_file = cls._get_container_info(
                    instance_id, log_name)

                head, body = swift_cli.get_container(container, prefix=prefix)
                log_obj_to_display = []

                if lines:
                    total_lines = lines
                    partial_results = False
                    parts = sorted(body, key=lambda obj: obj['last_modified'],
                                   reverse=True)

                    for part in parts:
                        obj_hdrs = swift_cli.head_object(
                            container,
                            part['name'])
                        obj_lines = int(obj_hdrs['x-object-meta-lines'])
                        log_obj_to_display.insert(0, part)
                        if obj_lines >= lines:
                            partial_results = True
                            break
                        lines -= obj_lines
                    if not partial_results:
                        lines = total_lines

                    part = log_obj_to_display.pop(0)
                    hdrs, log_obj = swift_cli.get_object(
                        container,
                        part['name'])
                    log_by_lines = log_obj.decode().splitlines()
                    yield "\n".join(log_by_lines[-1 * lines:]) + "\n"
                else:
                    # Show all the logs
                    log_obj_to_display = sorted(
                        body, key=lambda obj: obj['last_modified'])

                for log_part in log_obj_to_display:
                    headers, log_obj = swift_cli.get_object(
                        container,
                        log_part['name'])
                    yield log_obj.decode()
            except swift_client.ClientException as ex:
                if ex.http_status == 404:
                    raise trove_exc.GuestLogNotFound()
                raise trove_exc.TroveTempestException()

        return lambda: _log_generator(instance_id, log_name, lines)
