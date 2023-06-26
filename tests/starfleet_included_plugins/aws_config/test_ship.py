"""Tests for the AWS Config main ship entrypoints

Tests for the full end-to-end logic

:Module: starfleet.tests.starfleet_included_plugins.aws_config.test_ship
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
# pylint: disable=unused-argument,too-many-locals
import json
import os
from typing import Any, Dict
from unittest import mock
from unittest.mock import MagicMock

import pytest
from botocore.client import BaseClient
from click.testing import CliRunner

from starfleet.account_index.loader import AccountIndexInstance


def test_worker_configuration(test_configuration: Dict[str, Any]) -> None:
    """Tests that our configuration schema is working."""
    from starfleet.worker_ships.plugins.aws_config.ship import AwsConfigWorkerShip

    loaded = AwsConfigWorkerShip.configuration_template_class().load(test_configuration["AwsConfigWorkerShip"])
    assert loaded["worker_role_session_name"] == "StarfleetAwsConfigWorkerShip"
    assert loaded["worker_role_to_assume"] == "starfleet-worker-basic-test-role"


@pytest.mark.parametrize("commit", [False, True])
@pytest.mark.parametrize("cli", [False, True])
@pytest.mark.parametrize("region", ["us-east-1", "us-west-1"])
def test_ship(
    commit: bool,
    cli: bool,
    region: str,
    aws_config: BaseClient,
    template: Dict[str, Any],
    test_index: AccountIndexInstance,
    mock_slack_api: MagicMock,
    test_configuration: Dict[str, Any],
) -> None:
    """
    This performs the full test run of the worker for both the CLI and also the Lambda.

    This will test both the DefaultConfiguration and also the AccountOverrideConfiguration by separating 000000000001 per us-east-1 and us-west-1
    """
    from starfleet.worker_ships.plugins.aws_config.ship import AwsConfigWorkerShip, lambda_handler, aws_config as click_group
    from starfleet.worker_ships.plugins.aws_config.logic import get_current_state, determine_workload, RecorderAction

    if cli:
        runner = CliRunner()
        payload_file = __file__.split("test_ship.py", maxsplit=1)[0] + "test_payload.yaml"
        cmd_line_args = ["sync", "--payload", payload_file, "--account-id", "000000000001", "--region", region]

        if commit:
            cmd_line_args.append("--commit")

        result = runner.invoke(click_group, cmd_line_args)  # noqa
        assert not result.exception

    else:
        # Embed the Starbase account and region details in:
        template["StarbaseAssignedAccount"] = "000000000001"
        template["StarbaseAssignedRegion"] = region

        # Enable Slack:
        test_configuration["AwsConfigWorkerShip"]["AlertConfiguration"] = {"ChannelId": "pewpewpew", "AlertPriority": "INFORMATIONAL"}

        if commit:
            os.environ["STARFLEET_COMMIT"] = "true"

        lambda_handler({"Records": [{"body": json.dumps(template)}]}, object())  # pylint: disable=no-value-for-parameter

    # Get the current state for verification:
    current_state = get_current_state("000000000001", region, assume_role="SomeRole", session_name="SomeSession")

    if commit:
        # Verify that the alert code was called:
        if not cli:
            assert mock_slack_api.return_value.chat_postMessage.call_args.kwargs["text"] == "✅  Updated AWS Config properties"
            assert mock_slack_api.return_value.chat_postMessage.call_args.kwargs["blocks"][1]["text"]["text"].startswith(
                f"*Below is a summary of the work performed in 000000000001/{region}:*"
            )
            assert (
                "> 📼  Updated the Configuration Recorder. See the logs for details.\n> 🚚  Updated the Delivery Channel. See the logs for details.\n"
                + "> 🗄  Updated the Retention Configuration. See the logs for details.\n> ⏺️  Started the Configuration Recorder"
                in mock_slack_api.return_value.chat_postMessage.call_args.kwargs["blocks"][1]["text"]["text"]
            )

        # Verify that the state is correct by verifying the workload:
        if region == "us-west-1":
            working_template = AwsConfigWorkerShip.payload_template_class().load(template)["account_override_configurations"][0]
            assert current_state["RetentionConfig"] == {"Name": "default", "RetentionPeriodInDays": 30}

        else:
            working_template = AwsConfigWorkerShip.payload_template_class().load(template)["default_configuration"]
            assert current_state["RetentionConfig"] == {"Name": "default", "RetentionPeriodInDays": 2557}

        workload = determine_workload(current_state, working_template, "000000000001", region)
        assert workload == {"ConfigurationRecorder": {}, "DeliveryChannel": {}, "EnableRecording": RecorderAction.DO_NOTHING, "RetentionConfig": {}}

    else:
        # Nothing should be detected, and no alerts emitted:
        assert current_state == {"ConfigurationRecorder": {}, "DeliveryChannel": {}, "RecorderStatus": {}, "RetentionConfig": {}}
        assert not mock_slack_api.return_value.chat_postMessage.called

    # Clean up the env var:
    os.environ.pop("STARFLEET_COMMIT", None)


def test_error_alerts(
    template: Dict[str, Any],
    test_index: AccountIndexInstance,
    mock_slack_api: MagicMock,
    test_configuration: Dict[str, Any],
) -> None:
    """This just tests that we send an alert if there is an exception while processing the worker."""
    from starfleet.worker_ships.plugins.aws_config.ship import lambda_handler

    # Enable Slack:
    test_configuration["AwsConfigWorkerShip"]["AlertConfiguration"] = {"ChannelId": "pewpewpew", "AlertPriority": "INFORMATIONAL"}

    # Embed the account/region
    template["StarbaseAssignedAccount"] = "000000000001"
    template["StarbaseAssignedRegion"] = "us-east-1"

    # We are going to mock out the first externally called function to just return some exception.
    with mock.patch("starfleet.worker_ships.plugins.aws_config.ship.get_account_region_payload", side_effect=Exception("Some problem")):
        with pytest.raises(Exception):
            lambda_handler({"Records": [{"body": json.dumps(template)}]}, object())  # pylint: disable=no-value-for-parameter

    # Verify that we emitted the alert:
    assert (
        mock_slack_api.return_value.chat_postMessage.call_args.kwargs["text"] == "🚨  Problem updating AWS Config properties for template: AWSConfigEnablement"
    )
    assert (
        "*Unable to update the AWS Config configuration in: 000000000001/us-east-1.*"
        in mock_slack_api.return_value.chat_postMessage.call_args.kwargs["blocks"][1]["text"]["text"]
    )
    assert "```\nTraceback (most recent call last):" in mock_slack_api.return_value.chat_postMessage.call_args.kwargs["blocks"][1]["text"]["text"]
    assert "Exception: Some problem\n```" in mock_slack_api.return_value.chat_postMessage.call_args.kwargs["blocks"][1]["text"]["text"]
