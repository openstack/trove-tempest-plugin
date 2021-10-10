# Copyright (c) 2016 Hewlett-Packard Development Company, L.P.
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

from oslo_config import cfg

service_option = cfg.BoolOpt(
    'trove',
    default=True,
    help="Whether or not Trove is expected to be available"
)

database_group = cfg.OptGroup(
    name='database',
    title='Database Service Options'
)

DatabaseGroup = [
    cfg.StrOpt(
        'catalog_type',
        default='database',
        help="Catalog type of the Database service."
    ),
    cfg.StrOpt(
        'endpoint_type',
        default='publicURL',
        choices=['public', 'admin', 'internal', 'publicURL', 'adminURL',
                 'internalURL'],
        help="The endpoint type to use for the Database service."
    ),
    cfg.ListOpt(
        'enabled_datastores',
        default=['mysql']
    ),
    cfg.DictOpt(
        'default_datastore_versions',
        default={'mysql': '5.7.29'},
        help='The default datastore versions used to create instance',
    ),
    cfg.DictOpt(
        'pre_upgrade_datastore_versions',
        default={},
        help='The datastore versions used to create instances that need to be '
             'upgrade.',
    ),
    cfg.IntOpt('database_build_timeout',
               default=1800,
               help='Timeout in seconds to wait for a database instance to '
                    'build.'),
    cfg.IntOpt(
        'database_restore_timeout',
        default=3600,
        help='Timeout in seconds to wait for a database instance to '
             'be restored.'
    ),
    cfg.IntOpt(
        'backup_wait_timeout',
        default=600,
        help='Timeout in seconds to wait for a backup to be completed.'
    ),
    cfg.StrOpt(
        'flavor_id',
        default="d2",
        help="The Nova flavor ID used for creating database instance."
    ),
    cfg.StrOpt(
        'resize_flavor_id',
        default="d3",
        help="The Nova flavor ID used for resizing database instance."
    ),
    cfg.StrOpt(
        'shared_network',
        default="private",
        help=('Pre-defined network name or ID used for creating database '
              'instance.')
    ),
    cfg.StrOpt(
        'subnet_cidr',
        default='10.1.1.0/24',
        help=('The Neutron CIDR format subnet to use for database network '
              'creation.')
    ),
    cfg.StrOpt(
        'volume_type',
        default="lvmdriver-1",
        help="The Cinder volume type used for creating database instance."
    ),
    cfg.StrOpt(
        'database_log_container',
        default="database_logs",
        help="The name of Swift container for the database instance log, "
             "should be the same with the config in the cloud."
    ),
    cfg.BoolOpt(
        'remove_swift_account',
        default=True,
        help='If clean up the Swift account for test users after backup '
             'function test. ResellerAdmin should be added to tempest config '
             'option "tempest_roles".'
    ),
    cfg.StrOpt(
        'rebuild_image_id',
        help="The new guest image ID used for rebuilding database instance."
    ),
]
