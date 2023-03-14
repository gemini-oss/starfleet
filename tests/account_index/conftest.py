"""PyTest fixtures for Starfleet's Account Indexer Tests

This defines the PyTest fixtures for the Account Indexer tests

:Module: starfleet.tests.account_index.conftest
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
# pylint: disable=unused-argument
from typing import Generator, Any, Dict
from unittest import mock

import pytest

from starfleet.account_index.loader import StarfleetAccountIndexLoader, AccountIndexInstance
import tests.account_index.testing_plugins.basic_plugin


@pytest.fixture
def test_index(test_configuration: Dict[str, Any]) -> Generator[AccountIndexInstance, None, None]:
    """This returns the StarfleetAccountIndexLoader with a TestingAccountIndexPlugin configured for it."""
    account_indexer = StarfleetAccountIndexLoader()
    account_indexer._index_ship_path = tests.account_index.testing_plugins.__path__
    account_indexer._index_ship_prefix = tests.account_index.testing_plugins.__name__ + "."

    with mock.patch("starfleet.account_index.loader.ACCOUNT_INDEX", account_indexer):
        yield account_indexer.index
