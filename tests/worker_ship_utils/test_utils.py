"""Tests for worker ship utilities for both the CLI and Lambda

Tests that the CLI utilities are working properly and lambda function utilities are working properly.

:Module: starfleet.tests.worker_ship_utils.test_cli_utils
:Copyright: (c) 2022 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
import json

# pylint: disable=unused-argument

from typing import Dict, Any, TypeVar
from unittest import mock

import click
import pytest
from click.testing import CliRunner
from marshmallow import ValidationError

from starfleet.worker_ships.cli_utils import load_payload


@click.group()
def cli_testing_group() -> None:
    """This is a click CLI group used to test things out."""


@cli_testing_group.command()
@click.option("--payload", required=True, type=click.File("r"), callback=load_payload)
def unit_test(payload: Dict[str, Any]) -> None:
    """This is a command to test that things work."""
    assert payload


def test_load_payload(test_configuration: Dict[str, Any]) -> None:
    """This is a test to make sure that the load_payload command works properly."""
    runner = CliRunner()

    # Need to test with a file that exists:
    test_file = __file__.split("test_utils.py", maxsplit=1)[0] + "sample_payloads/sample_payload.yaml"
    result = runner.invoke(unit_test, ["--payload", test_file])
    assert result.exit_code == 0

    # Need to test with file that does not exist:
    result = runner.invoke(unit_test, ["--payload", "pew pew pew"])
    assert "Error: Invalid value for '--payload': 'pew pew pew': No such file or directory" in result.output

    # Need to test with a file that is empty:
    test_file = __file__.split("test_utils.py", maxsplit=1)[0] + "sample_payloads/empty_payload.yaml"
    result = runner.invoke(unit_test, ["--payload", test_file])
    assert "[💥] Problem loading the YAML template. See the stacktrace below!\nError: [💥] The loaded YAML is EMPTY!!" in result.output

    # With an invalid YAML:
    test_file = __file__.split("test_utils.py", maxsplit=1)[0] + "sample_payloads/invalid_yaml.yaml"
    result = runner.invoke(unit_test, ["--payload", test_file])
    assert "[💥] Problem loading the YAML template. See the stacktrace below!" in result.output


def test_worker_lambda_handler(test_configuration: Dict[str, Any]) -> None:
    """This tests that the worker_lambda decorator works properly."""
    from starfleet.worker_ships.lambda_utils import worker_lambda
    from starfleet.utils.configuration import BadConfigurationError
    from tests.worker_ship_utils.testing_plugins.basic_plugin import TestingStarfleetWorkerPlugin

    TestingStarfleetWorkerInstance = TypeVar("TestingStarfleetWorkerInstance", bound=TestingStarfleetWorkerPlugin)

    # Test with no errors:
    @worker_lambda(TestingStarfleetWorkerPlugin)
    def normal_func(event: Dict[str, Any], context: object, worker: TestingStarfleetWorkerInstance, commit: bool) -> None:  # noqa
        """Testing no errors."""
        assert json.loads(event["Records"][0]["body"])  # not loading or verifying the event in this function beyond json work.
        assert commit is False
        assert isinstance(worker, TestingStarfleetWorkerPlugin)

    event = {"Records": [{"body": '{"some": "event"}'}]}
    normal_func(event, object())  # pylint: disable=no-value-for-parameter

    # Test with an invalid payload:
    @worker_lambda(TestingStarfleetWorkerPlugin)
    def bad_payload(event: Dict[str, Any], context: object, worker: TestingStarfleetWorkerInstance, commit: bool) -> None:  # noqa
        """Testing with bad payload."""
        worker.load_template(event)

    with mock.patch("starfleet.worker_ships.lambda_utils.LOGGER") as mocked_logger:
        with pytest.raises(ValidationError):
            bad_payload(event, object())  # pylint: disable=no-value-for-parameter
    assert mocked_logger.error.call_args.args[0] == "[💥] Encountered major problem processing the payload. See the stacktrace for details!"

    # Test with an invalid configuration:
    test_configuration[TestingStarfleetWorkerPlugin.get_worker_ship_name()].pop("Enabled")
    with pytest.raises(BadConfigurationError) as err:
        normal_func(event, object())  # pylint: disable=no-value-for-parameter
    assert "Missing data for required field." in str(err.value)

    # Test with a missing configuration:
    test_configuration.pop(TestingStarfleetWorkerPlugin.get_worker_ship_name())
    with pytest.raises(BadConfigurationError) as err:
        normal_func(event, object())  # pylint: disable=no-value-for-parameter
    assert str(err.value) == "[💥] No configuration found for the worker"
