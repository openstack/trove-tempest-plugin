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
import time

from oslo_log import log as logging
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sqlalchemy
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


def init_engine(db_url):
    return sqlalchemy.create_engine(db_url)


class SQLClient(object):
    def __init__(self, conn_str):
        self.engine = init_engine(conn_str)

    def conn_execute(self, conn, cmds):
        if isinstance(cmds, str):
            result = conn.execute(cmds)
            # Returns a ResultProxy
            # https://docs.sqlalchemy.org/en/13/core/connections.html#sqlalchemy.engine.ResultProxy
            return result

        for cmd in cmds:
            conn.execute(cmd)

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
