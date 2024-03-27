"""Tests for worker ship utilities for both the CLI and Lambda

Tests that the CLI utilities are working properly and lambda function utilities are working properly.

:Module: starfleet.tests.worker_ship_utils.test_cli_utils
:Copyright: (c) 2022 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""

# pylint: disable=unused-argument,unused-import,too-many-locals
import json

from typing import Dict, Any, TypeVar
from unittest import mock

import click
import pytest
from click import Context
from click.testing import CliRunner
from marshmallow import ValidationError

from starfleet.account_index.schematics import AccountIndexInstance
from starfleet.worker_ships.cli_utils import load_payload
from tests.account_index.conftest import test_index  # noqa


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
    result = runner.invoke(cli_testing_group, ["unit-test", "--payload", test_file])
    assert result.exit_code == 0

    # Need to test with file that does not exist:
    result = runner.invoke(cli_testing_group, ["unit-test", "--payload", "pew pew pew"])
    assert "Error: Invalid value for '--payload': 'pew pew pew': No such file or directory" in result.output

    # Need to test with a file that is empty:
    test_file = __file__.split("test_utils.py", maxsplit=1)[0] + "sample_payloads/empty_payload.yaml"
    result = runner.invoke(cli_testing_group, ["unit-test", "--payload", test_file])
    assert "[💥] Problem loading the YAML template. See the stacktrace below!\nError: [💥] The loaded YAML is EMPTY!!" in result.output

    # With an invalid YAML:
    test_file = __file__.split("test_utils.py", maxsplit=1)[0] + "sample_payloads/invalid_yaml.yaml"
    result = runner.invoke(cli_testing_group, ["unit-test", "--payload", test_file])
    assert "[💥] Problem loading the YAML template. See the stacktrace below!" in result.output


def test_starfleet_single_invoke_command(test_index: AccountIndexInstance) -> None:  # noqa  # pylint: disable=redefined-outer-name
    """This tests that the StarfleetSingleInvokeCommand works."""
    from starfleet.worker_ships.cli_utils import BadWorkerError, BadWorkerTemplateError, StarfleetSingleInvokeCommand
    from starfleet.worker_ships.ship_schematics import StarfleetWorkerShip, WorkerShipPayloadBaseTemplate

    runner = CliRunner()

    bad_template = __file__.split("test_utils.py", maxsplit=1)[0] + "sample_payloads/invalid_base.yaml"
    good_template = __file__.split("test_utils.py", maxsplit=1)[0] + "sample_payloads/sample_payload.yaml"

    class SingleInvokeTestShip(StarfleetWorkerShip):  # pylint: disable=abstract-method
        """Testing for an SINGLE_INVOCATION worker"""

        payload_template_class = WorkerShipPayloadBaseTemplate

    @click.command(cls=StarfleetSingleInvokeCommand)
    def bad_command(**kwargs) -> None:  # noqa # pragma: no cover
        """A bad command that won't run"""

    # Without a payload:
    result = runner.invoke(bad_command)
    assert "Error: Missing option '--payload'" in result.output

    # With the payload but command lacks the proper context set:
    result = runner.invoke(bad_command, ["--payload", bad_template])
    assert isinstance(result.exception, BadWorkerError)

    # To be used later...
    instantiated_worker = SingleInvokeTestShip()

    @click.group()
    @click.pass_context
    def good_group(ctx: Context) -> None:
        """A good click command group"""
        ctx.obj = instantiated_worker

    @good_group.command(cls=StarfleetSingleInvokeCommand)
    @click.pass_context
    def good_command(ctx: Context, **kwargs) -> None:  # noqa
        """A good click command"""
        assert True

    # Template is invalid:
    result = runner.invoke(good_group, ["good-command", "--payload", bad_template])
    assert isinstance(result.exception, ValidationError)

    # Everything is correct:
    result = runner.invoke(good_group, ["good-command", "--payload", good_template])
    assert "🆗" in result.output

    # Finally, verify that we triple check the payload type:
    instantiated_worker.payload_template_class = str  # just put some random class in here.
    result = runner.invoke(good_group, ["good-command", "--payload", good_template])
    assert isinstance(result.exception, BadWorkerTemplateError)


def test_starfleet_account_command(test_index: AccountIndexInstance) -> None:  # noqa  # pylint: disable=redefined-outer-name
    """This tests that the StarfleetAccountCommand works."""
    from starfleet.worker_ships.cli_utils import BadWorkerError, BadWorkerTemplateError, StarfleetAccountCommand
    from starfleet.worker_ships.ship_schematics import StarfleetWorkerShip
    from starfleet.worker_ships.base_payload_schemas import BaseAccountPayloadTemplate

    runner = CliRunner()

    bad_template = __file__.split("test_utils.py", maxsplit=1)[0] + "sample_payloads/sample_payload.yaml"
    good_template = __file__.split("test_utils.py", maxsplit=1)[0] + "sample_payloads/sample_account_payload.yaml"

    class AccountTestShip(StarfleetWorkerShip):  # pylint: disable=abstract-method
        """Testing for an ACCOUNT-REGION worker"""

        payload_template_class = BaseAccountPayloadTemplate

    @click.command(cls=StarfleetAccountCommand)
    def bad_command(**kwargs) -> None:  # noqa # pragma: no cover
        """A bad command that won't run"""

    # Without a payload:
    result = runner.invoke(bad_command)
    assert "Error: Missing option '--payload'" in result.output

    # Without an account ID:
    result = runner.invoke(bad_command, ["--payload", bad_template])
    assert "Error: Missing option '--account-id'" in result.output

    # With all 2 but the bad command lacks the proper context set:
    result = runner.invoke(bad_command, ["--payload", bad_template, "--account-id", "012345678910"])
    assert isinstance(result.exception, BadWorkerError)

    # To be used later...
    instantiated_worker = AccountTestShip()

    @click.group()
    @click.pass_context
    def good_group(ctx: Context) -> None:
        """A good click command group"""
        ctx.obj = instantiated_worker

    @good_group.command(cls=StarfleetAccountCommand)
    @click.pass_context
    def good_command(ctx: Context, **kwargs) -> None:  # noqa
        """A good click command"""
        assert True

    # Template is invalid:
    result = runner.invoke(good_group, ["good-command", "--payload", bad_template, "--account-id", "012345678910"])
    assert isinstance(result.exception, ValidationError)

    # Valid Template, but not processing the account in question:
    result = runner.invoke(good_group, ["good-command", "--payload", good_template, "--account-id", "012345678910"])
    assert "The account provided is not applicable for this template." in result.output

    # Everything is correct:
    result = runner.invoke(good_group, ["good-command", "--payload", good_template, "--account-id", "000000000001"])
    assert "🆗" in result.output

    # Verify that the worker payload contains the proper account ID and region passed in from the successful run:
    assert instantiated_worker.payload["starbase_assigned_account"] == "000000000001"

    # Finally, verify that we triple check the payload type:
    instantiated_worker.payload_template_class = str  # just put some random class in here.
    result = runner.invoke(good_group, ["good-command", "--payload", good_template, "--account-id", "000000000001"])
    assert isinstance(result.exception, BadWorkerTemplateError)


def test_starfleet_account_region_command(test_index: AccountIndexInstance) -> None:  # noqa  # pylint: disable=redefined-outer-name
    """This tests that the StarfleetAccountRegionCommand works."""
    from starfleet.worker_ships.cli_utils import BadWorkerError, BadWorkerTemplateError, StarfleetAccountRegionCommand
    from starfleet.worker_ships.ship_schematics import StarfleetWorkerShip
    from starfleet.worker_ships.base_payload_schemas import BaseAccountPayloadTemplate, BaseAccountRegionPayloadTemplate

    runner = CliRunner()

    bad_template = __file__.split("test_utils.py", maxsplit=1)[0] + "sample_payloads/sample_payload.yaml"
    good_template = __file__.split("test_utils.py", maxsplit=1)[0] + "sample_payloads/sample_account_region_payload.yaml"

    class AccountRegionTestShip(StarfleetWorkerShip):  # pylint: disable=abstract-method
        """Testing for an ACCOUNT-REGION worker"""

        payload_template_class = BaseAccountRegionPayloadTemplate

    @click.command(cls=StarfleetAccountRegionCommand)
    def bad_command(**kwargs) -> None:  # noqa # pragma: no cover
        """A bad command that won't run"""

    # Without a payload:
    result = runner.invoke(bad_command)
    assert "Error: Missing option '--payload'" in result.output

    # Without an account ID:
    result = runner.invoke(bad_command, ["--payload", bad_template])
    assert "Error: Missing option '--account-id'" in result.output

    # Without the region:
    result = runner.invoke(bad_command, ["--payload", bad_template, "--account-id", "012345678910"])
    assert "Error: Missing option '--region'" in result.output

    # With all 3 but the bad command lacks the proper context set:
    result = runner.invoke(bad_command, ["--payload", bad_template, "--account-id", "012345678910", "--region", "us-east-1"])
    assert isinstance(result.exception, BadWorkerError)

    # To be used later...
    instantiated_worker = AccountRegionTestShip()

    @click.group()
    @click.pass_context
    def good_group(ctx: Context) -> None:
        """A good click command group"""
        ctx.obj = instantiated_worker

    @good_group.command(cls=StarfleetAccountRegionCommand)
    @click.pass_context
    def good_command(ctx: Context, **kwargs) -> None:  # noqa
        """A good click command"""
        assert True

    # Template is invalid:
    result = runner.invoke(good_group, ["good-command", "--payload", bad_template, "--account-id", "012345678910", "--region", "us-east-1"])
    assert isinstance(result.exception, ValidationError)

    # Valid Template, but not processing the account and region in question:
    result = runner.invoke(good_group, ["good-command", "--payload", good_template, "--account-id", "012345678910", "--region", "us-east-1"])
    assert "The account/region provided is not applicable for this template." in result.output

    # Valid Template, but not processing the region in question:
    result = runner.invoke(good_group, ["good-command", "--payload", good_template, "--account-id", "111111111111", "--region", "us-west-1"])
    assert "The account/region provided is not applicable for this template." in result.output

    # Everything is correct:
    result = runner.invoke(good_group, ["good-command", "--payload", good_template, "--account-id", "000000000001", "--region", "us-east-1"])
    assert "🆗" in result.output

    # Verify that the worker payload contains the proper account ID and region passed in from the successful run:
    assert instantiated_worker.payload["starbase_assigned_account"] == "000000000001"
    assert instantiated_worker.payload["starbase_assigned_region"] == "us-east-1"

    # Finally, verify that we triple check the payload type:
    instantiated_worker.payload_template_class = BaseAccountPayloadTemplate
    result = runner.invoke(good_group, ["good-command", "--payload", good_template, "--account-id", "000000000001", "--region", "us-east-1"])
    assert isinstance(result.exception, BadWorkerTemplateError)


def test_worker_lambda_handler(test_configuration: Dict[str, Any]) -> None:
    """This tests that the worker_lambda decorator works properly."""
    from starfleet.worker_ships.lambda_utils import worker_lambda
    from starfleet.utils.configuration import BadConfigurationError
    from tests.worker_ship_utils.testing_plugins.basic_plugin import TestingStarfleetWorkerPlugin
    from starfleet.worker_ships.ship_schematics import AlertPriority

    TestingStarfleetWorkerInstance = TypeVar("TestingStarfleetWorkerInstance", bound=TestingStarfleetWorkerPlugin)

    # Test with no errors (no alert configuration supplied):
    @worker_lambda(TestingStarfleetWorkerPlugin)
    def normal_func(event: Dict[str, Any], context: object, worker: TestingStarfleetWorkerInstance, commit: bool) -> None:  # noqa
        """Testing no errors."""
        assert json.loads(event["Records"][0]["body"])  # not loading or verifying the event in this function beyond json work.
        assert commit is False
        assert isinstance(worker, TestingStarfleetWorkerPlugin)
        assert not worker.alert_channel
        assert worker.alert_priority == AlertPriority.NONE

    event = {"Records": [{"body": '{"some": "event"}'}]}
    normal_func(event, object())  # pylint: disable=no-value-for-parameter

    # Test with an alert configuration supplied:
    test_configuration[TestingStarfleetWorkerPlugin.get_worker_ship_name()]["AlertConfiguration"] = {"ChannelId": "lol", "AlertPriority": "SUCCESS"}

    @worker_lambda(TestingStarfleetWorkerPlugin)
    def alert_config_func(event: Dict[str, Any], context: object, worker: TestingStarfleetWorkerInstance, commit: bool) -> None:  # noqa
        """Testing with an alert configuration:"""
        assert worker.alert_channel == "lol"
        assert worker.alert_priority == AlertPriority.SUCCESS

    alert_config_func(event, object())  # pylint: disable=no-value-for-parameter

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
