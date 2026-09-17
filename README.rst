====================
Trove Tempest Plugin
====================

.. image:: https://governance.openstack.org/tc/badges/trove-tempest-plugin.svg

.. Change things from this point on

Tempest plugin for Trove Project

It contains tempest tests for Trove project.

* Free software: Apache license
* Documentation: https://docs.openstack.org/trove/latest/
* Source: https://opendev.org/openstack/trove-tempest-plugin
* Bugs: https://bugs.launchpad.net/trove

Installing
----------

Clone this repository, and call from the repo::

    $ python3 -m pip install -e .

Requirements
------------

Install barbican tempest plugin::

    $ git clone https://opendev.org/openstack/barbican-tempest-plugin
    $ python3 -m pip install -e barbican-tempest-plugin

Configuring
-----------

Configure the environment setup options in the ``[database]`` section of
``tempest.conf``. For example:

.. code-block:: ini

    [database]
    ensure_quotas = instances:20,ram:10000,backups:10,volumes:-1
    ensure_barbican_quotas = secrets:500,containers:-1
    dns_nameservers = 10.0.0.53,10.0.0.54

Quota options specify minimum project limits. Existing higher or unlimited
limits are preserved; ``-1`` requests an unlimited quota. Empty dictionaries
disable quota changes. The administrative credentials must have permission
to update quotas in the corresponding service.

``dns_nameservers`` applies only to newly created test subnets. Set
``shared_network`` to an empty value to create a test network; when using an
existing shared network, configure its DNS servers separately.

Running the tests
-----------------

To run all the tests from this plugin, call from the tempest repo::

    $ tox -e all -- trove_tempest_plugin

To run a single test case, call with full path, for example::

    $ tox -e all -- trove-tempest-plugin.blob.master.trove_tempest_plugin.tests.api.test_flavors.DatabaseFlavorsTest.test_get_db_flavor

To retrieve a list of all tempest tests, run::

    $ testr list-tests
