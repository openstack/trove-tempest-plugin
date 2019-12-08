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
    cfg.IntOpt('database_build_timeout',
               default=1800,
               help='Timeout in seconds to wait for a database instance to '
                    'build.'),
    cfg.StrOpt(
        'flavor_id',
        default="d2",
        help="The Nova flavor ID used for creating database instance."
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
]
