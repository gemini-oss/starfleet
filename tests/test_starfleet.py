"""Base tests for Starfleet.

:Module: starfleet.tests.test_starfleet
:Copyright: (c) 2022 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""

import pytest


def test_app_startup() -> None:
    """This tests that the application start up is able to load the utils properly."""
    from starfleet.startup import STARFLEET_CONFIGURATION, base_start_up

    base_start_up()

    # Test that we have a proper utils loaded (not a super sophisticated test):
    assert STARFLEET_CONFIGURATION.config["STARFLEET"]


def test_find_plugins() -> None:
    """This tests the find_plugins loading capability."""
    import tests.worker_ship_utils.testing_plugins
    from tests.worker_ship_utils.testing_plugins.basic_plugin import WORKER_SHIP_PLUGINS
    from starfleet.utils.plugin_loader import find_plugins
    from starfleet.worker_ships.ship_schematics import StarfleetWorkerShip

    plugins = find_plugins(
        tests.worker_ship_utils.testing_plugins.__path__,  # noqa
        tests.worker_ship_utils.testing_plugins.__name__ + ".",
        "WORKER_SHIP_PLUGINS",
        StarfleetWorkerShip,
    )

    # Iterate over the module components and pull out the StarfleetWorkerShip objects:
    assert len(plugins) == 1
    assert plugins["tests.worker_ship_utils.testing_plugins.basic_plugin"] == WORKER_SHIP_PLUGINS
    assert issubclass(plugins["tests.worker_ship_utils.testing_plugins.basic_plugin"][0], StarfleetWorkerShip)


def test_find_plugin_exceptions() -> None:
    """This tests that exceptions are properly raised in the find_plugins function.

    Possible TODO: If this causes errors, it may likely be because of concurrent test execution. If that happens, then make a separate package just for the
    bad plugin and pass in that path to not interfere with `starfleet.tests.worker_ship_utils.testing_plugins`. If not, then just leave it as is ;)
    """
    import tests.worker_ship_utils.testing_plugins
    import tests.worker_ship_utils.testing_plugins.bad_plugin
    from starfleet.utils.plugin_loader import find_plugins, InvalidPluginClassException, InvalidPluginListException
    from starfleet.worker_ships.ship_schematics import StarfleetWorkerShip

    # First test that if we don't have a list in for the WORKER_SHIP_NAME (the plugin_attr_name) that this will fail (this is adding the field, so can't use mock):
    tests.worker_ship_utils.testing_plugins.bad_plugin.WORKER_SHIP_PLUGINS = "pew pew pew"
    with pytest.raises(InvalidPluginListException) as exc:
        find_plugins(
            tests.worker_ship_utils.testing_plugins.__path__,  # noqa
            tests.worker_ship_utils.testing_plugins.__name__ + ".",
            "WORKER_SHIP_PLUGINS",
            StarfleetWorkerShip,
        )
    assert (
        str(exc.value) == "[💥] The package: tests.worker_ship_utils.testing_plugins.bad_plugin needs a variable named WORKER_SHIP_PLUGINS that is of type "
        "List, not type: <class 'str'>"
    )

    # Next, we are going to test that if we have a class name in WORKER_SHIP_NAME that is not based on StarfleetWorkerShip, that it will fail:
    tests.worker_ship_utils.testing_plugins.bad_plugin.WORKER_SHIP_PLUGINS = [str]
    with pytest.raises(InvalidPluginClassException) as exc:
        find_plugins(
            tests.worker_ship_utils.testing_plugins.__path__,  # noqa
            tests.worker_ship_utils.testing_plugins.__name__ + ".",
            "WORKER_SHIP_PLUGINS",
            StarfleetWorkerShip,
        )
    assert (
        str(exc.value) == "[💥] The plugin: str in package: tests.worker_ship_utils.testing_plugins.bad_plugin does not properly subclass: StarfleetWorkerShip"
    )

    # Clean Up just to be on the safe side for future tests:
    del tests.worker_ship_utils.testing_plugins.bad_plugin.WORKER_SHIP_PLUGINS  # noqa
    assert not hasattr(tests.worker_ship_utils.testing_plugins.bad_plugin, "WORKER_SHIP_PLUGINS")
