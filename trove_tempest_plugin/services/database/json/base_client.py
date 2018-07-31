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

from oslo_serialization import jsonutils as json
from six.moves.urllib import parse as urllib

from tempest.lib.common import rest_client


class BaseClient(rest_client.RestClient):

    def show_resource(self, uri, expected_status_code=200, **fields):
        if fields:
            # Encode provided dict of fields into a series of key=value pairs
            # separated by '&' characters.
            #
            # The field value can be a sequence. Setting option doseq to True
            # enforces producing individual key-value pair for each element of
            # the sequence under the same key.
            #
            # e.g. {'foo': 'bar', 'baz': ['test1', 'test2']}
            #      => foo=bar&baz=test1&baz=test2
            uri += '?' + urllib.urlencode(fields, doseq=True)
        resp, body = self.get(uri)
        self.expected_success(expected_status_code, resp.status)
        body = json.loads(body)
        return rest_client.ResponseBody(resp, body)

    def list_resources(self, uri, expected_status_code=200, **filters):
        if filters:
            uri += '?' + urllib.urlencode(filters, doseq=True)
        resp, body = self.get(uri)
        self.expected_success(expected_status_code, resp.status)
        body = json.loads(body)
        return rest_client.ResponseBody(resp, body)
