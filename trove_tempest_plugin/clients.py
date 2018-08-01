# Copyright 2018 Samsung Electronics
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
from tempest.lib.services import clients

CONF = config.CONF


class Manager(clients.ServiceClients):
    """Service clients proxy.

    Enhances tests with a convenient way to access available service clients
    configured for a specified set of credentials.
    """

    def __init__(self, credentials, service=None):
        if CONF.identity.auth_version == 'v2':
            identity_uri = CONF.identity.uri
        else:
            identity_uri = CONF.identity.uri_v3
        super(Manager, self).__init__(credentials, identity_uri)
