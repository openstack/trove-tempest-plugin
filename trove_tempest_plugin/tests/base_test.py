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

from tempest import config
from tempest import test

from trove_tempest_plugin import clients

CONF = config.CONF


class BaseDatabaseTest(test.BaseTestCase):
    """Base test case class.

    Includes parts common to API and scenario tests:
        * test case callbacks,
        * service clients initialization.
    """

    credentials = ['primary']
    client_manager = clients.Manager

    @classmethod
    def skip_checks(cls):
        super(BaseDatabaseTest, cls).skip_checks()
        if not CONF.service_available.trove:
            skip_msg = ("%s skipped as trove is not available" % cls.__name__)
            raise cls.skipException(skip_msg)

    @classmethod
    def setup_clients(cls):
        """Setups service clients.

        Tempest provides a convenient fabrication interface, which can be used
        to produce instances of clients configured with the required parameters
        and a selected set of credentials. Thanks to this interface, the
        complexity of client initialization is hidden from the developer. All
        parameters such as "catalog_type", "auth_provider", "build_timeout"
        etc. are read from Tempest configuration and then automatically
        installed in the clients.

        The fabrication interface is enabled through the client manager, which
        is hooked to the class by the "client_manager" property.

        To initialize a new client, one need to specify the set of credentials
        (primary, admin) to be used and the category of client (eg compute,
        image, database, etc.). Together, they constitute a proxy for the
        fabricators of specific client classes from a given category.

        For example, initializing a new flavors client from the database
        category with primary privileges boils down to the following call:

        flavors_client = cls.os_primary.database.FlavorsClient()

        In order to initialize a new networks client from the compute category
        with administrator privilages:

        networks_client = cls.os_admin.compute.NetworksClient()

        Note, that selected set of credentials must be declared in the
        "credentials" property of this class.
        """
        super(BaseDatabaseTest, cls).setup_clients()
        cls.database_flavors_client = cls.os_primary.database.FlavorsClient()
        cls.os_flavors_client = cls.os_primary.compute.FlavorsClient()
        cls.database_limits_client = cls.os_primary.database.LimitsClient()
        cls.database_versions_client = cls.os_primary.database.VersionsClient()

    @classmethod
    def resource_setup(cls):
        super(BaseDatabaseTest, cls).resource_setup()
        cls.catalog_type = CONF.database.catalog_type
        cls.db_flavor_ref = CONF.database.db_flavor_ref
        cls.db_current_version = CONF.database.db_current_version
