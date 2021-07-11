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

from urllib import parse as urlparse

from oslo_serialization import jsonutils as json
import tenacity

from tempest.lib.common import rest_client
from tempest.lib import exceptions


class TroveClient(rest_client.RestClient):
    def __init__(self, auth_provider, **kwargs):
        super(TroveClient, self).__init__(auth_provider, **kwargs)

    def get_resource(self, obj, id, expected_status_code=200):
        url = '/%s/%s' % (obj, id)
        resp, body = self.get(url)
        self.expected_success(expected_status_code, resp.status)

        return rest_client.ResponseBody(resp, json.loads(body))

    def list_resources(self, obj, expected_status_code=200, **filters):
        url = '/%s' % obj
        if filters:
            # Encode provided dict of fields into a series of key=value pairs
            # separated by '&' characters.
            #
            # The field value can be a sequence. Setting option doseq to True
            # enforces producing individual key-value pair for each element of
            # the sequence under the same key.
            #
            # e.g. {'foo': 'bar', 'baz': ['test1', 'test2']}
            #      => foo=bar&baz=test1&baz=test2
            url += '?' + urlparse.urlencode(filters, doseq=True)

        resp, body = self.get(url)
        self.expected_success(expected_status_code, resp.status)

        return rest_client.ResponseBody(resp, json.loads(body))

    @tenacity.retry(
        wait=tenacity.wait_fixed(5),
        stop=tenacity.stop_after_attempt(2),
        retry=tenacity.retry_if_exception_type(),
        reraise=True
    )
    def delete_resource(self, obj, id, ignore_notfound=False):
        try:
            resp, _ = self.delete('/{obj}/{id}'.format(obj=obj, id=id))
            self.expected_success(202, resp.status)
            return resp
        except exceptions.NotFound:
            if ignore_notfound:
                return None
            else:
                raise

    def force_delete_instance(self, id):
        headers = {"Content-Type": "application/json"}
        body = {"reset_status": {}}
        resp, _ = self.post(f'/instances/{id}/action', json.dumps(body),
                            headers=headers)
        self.expected_success(202, resp.status)

        self.delete_resource('instances', id, ignore_notfound=True)

    def create_resource(self, obj, req_body, extra_headers={},
                        expected_status_code=200, need_response=True):
        headers = {"Content-Type": "application/json"}
        headers = dict(headers, **extra_headers)
        url = '/%s' % obj

        resp, body = self.post(url, json.dumps(req_body), headers=headers)
        self.expected_success(expected_status_code, resp.status)

        if need_response:
            return rest_client.ResponseBody(resp, json.loads(body))

    def patch_resource(self, obj, id, req_body, expected_status_code=202):
        url = '/{obj}/{id}'.format(obj=obj, id=id)
        headers = {"Content-Type": "application/json"}

        resp, _ = self.patch(url, json.dumps(req_body), headers=headers)
        self.expected_success(expected_status_code, resp.status)

    def put_resource(self, url, req_body, expected_status_code=202):
        url = '/%s' % url
        headers = {"Content-Type": "application/json"}

        resp, _ = self.put(url, json.dumps(req_body), headers=headers)
        self.expected_success(expected_status_code, resp.status)
