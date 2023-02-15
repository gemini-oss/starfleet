"""Tests for Stafleet's generic Account Index components

Tests for the account index components, like the plugin loader

:Module: starfleet.tests.account_index.test_account_index_components
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
# pylint: disable=unused-argument
from typing import Any, Dict

import pytest

from starfleet.account_index.loader import AccountIndexInstance


def test_load_good_plugin(test_index: AccountIndexInstance) -> None:
    """This tests that the good testing plugin loads properly. This also tests the fixture."""
    assert "000000000020" in test_index.get_all_accounts()


def test_loading_invalid_subclass(test_configuration: Dict[str, Any]) -> None:
    """This tests that we properly handle exceptions related to incorrect subclasses."""
    from starfleet.account_index.loader import StarfleetAccountIndexLoader
    from starfleet.utils.plugin_loader import InvalidPluginClassException
    import tests.account_index.testing_plugins.bad_plugin

    index_loader = StarfleetAccountIndexLoader()
    index_loader._index_ship_path = tests.account_index.testing_plugins.__path__
    index_loader._index_ship_prefix = tests.account_index.testing_plugins.__name__ + "."

    # Test one that doesn't properly subclass the AccountIndex:
    class FakePlugin:
        """This is a fake plugin used for testing."""

    fake_account_index_plugins = [FakePlugin]
    tests.account_index.testing_plugins.bad_plugin.ACCOUNT_INDEX_PLUGINS = fake_account_index_plugins
    with pytest.raises(InvalidPluginClassException) as exc:
        index_loader.load_indexes()
    assert str(exc.value).endswith("does not properly subclass: AccountIndex")

    del tests.account_index.testing_plugins.bad_plugin.ACCOUNT_INDEX_PLUGINS  # noqa
    assert not hasattr(tests.account_index.testing_plugins.bad_plugin, "ACCOUNT_INDEX_PLUGINS")


def test_loading_invalid_configuration(test_configuration: Dict[str, Any]) -> None:
    """This tests that the Starfleet configuration is set to load a plugin that exists."""
    from starfleet.account_index.loader import StarfleetAccountIndexLoader, UnknownAccountIndexError
    import tests.account_index.testing_plugins

    test_configuration["STARFLEET"]["AccountIndex"] = "FakePlugin"
    index_loader = StarfleetAccountIndexLoader()
    index_loader._index_ship_path = tests.account_index.testing_plugins.__path__
    index_loader._index_ship_prefix = tests.account_index.testing_plugins.__name__ + "."

    with pytest.raises(UnknownAccountIndexError) as exc:
        _ = index_loader.index

    assert str(exc.value) == "FakePlugin"
