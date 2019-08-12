====================
Trove Tempest Plugin
====================

.. image:: https://governance.openstack.org/tc/badges/trove-tempest-plugin.svg

.. Change things from this point on

Tempest plugin for Trove Project

It contains tempest tests for Trove project.

* Free software: Apache license
* Documentation: https://docs.openstack.org/trove/latest/
* Source: https://git.openstack.org/cgit/openstack/trove-tempest-plugin
* Bugs: https://bugs.launchpad.net/trove

Installing
----------

Clone this repository, and call from the repo::

    $ python3 -m pip install -e .

Running the tests
-----------------

To run all the tests from this plugin, call from the tempest repo::

    $ tox -e all -- trove_tempest_plugin

To run a single test case, call with full path, for example::

    $ tox -e all -- trove-tempest-plugin.blob.master.trove_tempest_plugin.tests.api.test_flavors.DatabaseFlavorsTest.test_get_db_flavor

To retrieve a list of all tempest tests, run::

    $ testr list-tests
