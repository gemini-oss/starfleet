"""PyTest fixtures for the starfleet package.

This defines the PyTest fixtures that can be used by all starfleet tests.

:Module: starfleet.tests.conftest
:Copyright: (c) 2022 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
# pylint: disable=redefined-outer-name,unused-argument
import os

from typing import Any, Dict, Generator, Callable
from unittest import mock

import boto3
import pytest
from botocore.client import BaseClient
from moto import mock_sts, mock_secretsmanager

import tests
import tests.worker_ship_utils.testing_plugins
from starfleet.cli.components import StarfleetCliLoader
from starfleet.worker_ships.loader import StarfleetWorkerShipLoader


@pytest.fixture
def test_configuration() -> Generator[Dict[str, Any], None, None]:
    """Fixture with a test configuration loader for use in unit tests."""
    from starfleet.utils.configuration import STARFLEET_CONFIGURATION

    old_value = STARFLEET_CONFIGURATION._configuration_path
    STARFLEET_CONFIGURATION._configuration_path = f"{tests.__path__[0]}/test_configuration_files"  # noqa
    STARFLEET_CONFIGURATION._app_config = None

    yield STARFLEET_CONFIGURATION.config

    STARFLEET_CONFIGURATION._app_config = None
    STARFLEET_CONFIGURATION._configuration_path = old_value


@pytest.fixture
def test_worker_ship_loader(test_configuration: Dict[str, Any]) -> StarfleetWorkerShipLoader:
    """This is a fixture that will return a StarfleetWorkerShipLoader instance with the paths set to the testing plugin paths."""

    loader = StarfleetWorkerShipLoader()
    loader._worker_ship_path = tests.worker_ship_utils.testing_plugins.__path__
    loader._worker_ship_prefix = tests.worker_ship_utils.testing_plugins.__name__ + "."

    return loader


@pytest.fixture
def test_cli_loader(test_worker_ship_loader: StarfleetWorkerShipLoader) -> Generator[StarfleetCliLoader, None, None]:
    """Mocks out the CLI loader -- this also sets up the test worker ship loader"""
    with mock.patch("starfleet.cli.components.STARFLEET_WORKER_SHIPS", test_worker_ship_loader):
        new_cli_loader = StarfleetCliLoader()
        new_cli_loader._worker_ship_path = test_worker_ship_loader._worker_ship_path
        new_cli_loader._worker_ship_prefix = test_worker_ship_loader._worker_ship_prefix

        # Need to mock out the CLI:
        with mock.patch("starfleet.cli.components.STARFLEET_CLI_LOADER", new_cli_loader):
            yield new_cli_loader


@pytest.fixture
def aws_credentials() -> None:
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-2"


@pytest.fixture
def aws_sts(aws_credentials: None) -> BaseClient:
    """This is a fixture for a Moto wrapped AWS STS mock for the entire unit test."""
    with mock_sts():
        yield boto3.client("sts", region_name="us-east-2")


@pytest.fixture
def aws_secretsmanager(aws_credentials: None) -> BaseClient:
    """This is a fixture for a Moto wrapped AWS SecretsManager mock for the entire unit test."""
    with mock_secretsmanager():
        yield boto3.client("secretsmanager", region_name="us-east-2")


@pytest.fixture
def mock_retry() -> None:
    """
    This mocks out the retry decorator so things don't block.

    NOTE: GOTCHA ALERT:
    This fixture must be run **BEFORE** you import from a file that contains the @retry decorator. This is because this mocks out the original function.
    When imported AFTER the fixture is set, then you are importing the mocked out @retry decorator. If you import from a file with the @retry decorator in it
    BEFORE this fixture is set, then the function is decorated with the original @retry decorator. This is due to the way that Python imports work
    where the Python package stores the reference to the imported item. Mocking out *the original* place does not override the local package's reference
    to the dependency -- only mocking out the *the local* package import would do that.

    In this case, we want to mock out the original such that we don't have to make N fixtures for each and every place that uses @retry. This means you
    need to be careful about the imports in conftest.py and other places to ensure that mock_retry is set before the imports are run in the target place.

    ## ALSO NOTE: This runs on *each and every* test -- set in pytest.ini
    """

    def mock_retry_decorator(*args, **kwargs) -> Callable:  # noqa
        """This mocks out the retry decorator."""

        def retry(func: Callable) -> Callable:
            """This is the mocked out retry function itself that doesn't do anything."""
            return func

        return retry

    with mock.patch("retry.retry", mock_retry_decorator):
        yield
