"""Tests for the IAM Role worker ship

All the tests for the IAM Role worker ship entrypoints.

:Module: starfleet.tests.starfleet_included_plugins.iam.test_role_ship
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
# pylint: disable=unused-argument,unused-import,redefined-outer-name,too-many-locals,no-value-for-parameter,too-many-statements
import json
import os
from typing import Any, Dict
from unittest import mock
from unittest.mock import MagicMock

from botocore.client import BaseClient
from click.testing import CliRunner
import pytest
from marshmallow import ValidationError as MarshmallowError
from pydantic import ValidationError as PydanticError

from starfleet.account_index.loader import AccountIndexInstance


def test_validate_iambic_template_cli(test_index: AccountIndexInstance) -> None:
    """This tests the functionality of the CLI for validating the iambic template for IAM roles."""
    from starfleet.worker_ships.plugins.iam import iam as click_group

    runner = CliRunner()
    payload_file = __file__.split("test_role_ship.py", maxsplit=1)[0] + "test_role_payload.yaml"
    cmd_line_args = ["role", "validate-iambic", "--payload", payload_file]

    with mock.patch("starfleet.worker_ships.plugins.iam.role_ship.LOGGER") as mocked_logger:
        # Valid template:
        result = runner.invoke(click_group, cmd_line_args)
        assert result.exit_code == 0
        mocked_logger.info.assert_any_call("[✅] The template is valid!")
        mocked_logger.reset_mock()

        # Invalid Marshmallow validation template:
        payload_file = __file__.split("test_role_ship.py", maxsplit=1)[0] + "bad_payloads/bad_role_marshmallow.yaml"
        cmd_line_args = ["role", "validate-iambic", "--payload", payload_file]
        result = runner.invoke(click_group, cmd_line_args)
        assert result.exit_code == -1
        assert mocked_logger.error.call_args[0][0].startswith("[❌] The template is invalid: Found forbidden key: included_accounts")
        mocked_logger.reset_mock()

        # Invalid iambic template validation:
        payload_file = __file__.split("test_role_ship.py", maxsplit=1)[0] + "bad_payloads/bad_role_iambic.yaml"
        cmd_line_args = ["role", "validate-iambic", "--payload", payload_file]
        result = runner.invoke(click_group, cmd_line_args)
        assert result.exit_code == -1
        assert mocked_logger.error.call_args[0][0].startswith("[❌] The template failed iambic validation:")


@pytest.mark.parametrize("cli", [True, False])
def test_sync_with_no_role(
    cli: bool,
    aws_iam: BaseClient,
    aws_sts: BaseClient,
    test_index: AccountIndexInstance,
    template: Dict[str, Any],
    test_configuration: Dict[str, Any],
    mock_slack_api: MagicMock,
) -> None:
    """This will test the lambda and also the CLI for creating a role that doesn't presently exist."""
    from starfleet.worker_ships.plugins.iam import iam as click_group
    from starfleet.worker_ships.plugins.iam.role_ship import lambda_handler

    if cli:
        runner = CliRunner()
        payload_file = __file__.split("test_role_ship.py", maxsplit=1)[0] + "test_role_payload.yaml"
        cmd_line_args = ["role", "sync", "--payload", payload_file, "--account-id", "000000000001"]

    else:
        template["StarbaseAssignedAccount"] = "000000000001"

        # Enable Slack:
        test_configuration["IamRoleWorkerShip"]["AlertConfiguration"] = {"ChannelId": "pewpewpew", "AlertPriority": "INFORMATIONAL"}

    with mock.patch("starfleet.worker_ships.plugins.iam.role_ship.LOGGER") as mocked_logger:
        # Valid template:
        if cli:
            result = runner.invoke(click_group, cmd_line_args)
            assert result.exit_code == 0
        else:
            lambda_handler({"Records": [{"body": json.dumps(template)}]}, object())  # pylint: disable=no-value-for-parameter

        mocked_logger.info.assert_any_call(
            "[📝] The following changes would have been made if the commit flag was set:\nField: The entire role -- the role was missing and was created."
        )

        # Make sure that the role was _not_ created:
        assert not aws_iam.list_roles()["Roles"]
        mocked_logger.reset_mock()

        # Now, let's try with the commit flag:
        if cli:
            cmd_line_args.append("--commit")
            result = runner.invoke(click_group, cmd_line_args)
            assert result.exit_code == 0
        else:
            os.environ["STARFLEET_COMMIT"] = "true"
            lambda_handler({"Records": [{"body": json.dumps(template)}]}, object())  # pylint: disable=no-value-for-parameter
            assert (
                mock_slack_api.return_value.chat_postMessage.call_args.kwargs["text"] == "📣  IAM Role: StarfleetIambicTesting in Account 1 was created/updated"
            )
            assert "Field: The entire role" in mock_slack_api.return_value.chat_postMessage.call_args.kwargs["blocks"][1]["text"]["text"]

        mocked_logger.info.assert_any_call("[📝] The following changes have been made:\nField: The entire role -- the role was missing and was created.")

        # Verify that the role was created properly:
        assert len(aws_iam.list_roles()["Roles"]) == 1
        role_details = aws_iam.get_role(RoleName="StarfleetIambicTesting")["Role"]

        missing_tags = [{"Key": "owner", "Value": "pewpewpew"}, {"Key": "some_other_key", "Value": "some_other_value"}]
        for tag in role_details["Tags"]:
            missing_tags.remove(tag)
        assert not missing_tags
        assert role_details["Description"] == "Starfleet iambic test role with variable some_value"

        # No inline policies should be present for this role in Account 1:
        assert not aws_iam.list_role_policies(RoleName="StarfleetIambicTesting")["PolicyNames"]
        mocked_logger.reset_mock()

        # Try this again -- no changes should be detected:
        if cli:
            result = runner.invoke(click_group, cmd_line_args)
            assert result.exit_code == 0
        else:
            lambda_handler({"Records": [{"body": json.dumps(template)}]}, object())
        mocked_logger.info.assert_any_call("[⏭️] No changes detected. Nothing to do.")
        mocked_logger.reset_mock()

        # Try this in account 11:
        os.environ["MOTO_ACCOUNT_ID"] = "000000000011"
        if cli:
            cmd_line_args = ["role", "sync", "--payload", payload_file, "--account-id", "000000000011", "--commit"]
            result = runner.invoke(click_group, cmd_line_args)
            assert result.exit_code == 0
        else:
            template["StarbaseAssignedAccount"] = "000000000011"
            lambda_handler({"Records": [{"body": json.dumps(template)}]}, object())
        mocked_logger.info.assert_any_call("[📝] The following changes have been made:\nField: The entire role -- the role was missing and was created.")

        # Make sure that the special inline policy was added in this account -- this tests that account include/exclude logic is working properly as well:
        policies = aws_iam.list_role_policies(RoleName="StarfleetIambicTesting")["PolicyNames"]
        assert policies == ["SomePolicyIn-Account11"]

        os.environ.pop("STARFLEET_COMMIT", None)


def test_sync_existing_role(test_role: None, aws_iam: BaseClient, test_index: AccountIndexInstance, template: Dict[str, Any]) -> None:
    """This tests the logic for syncing an existing role."""
    from starfleet.worker_ships.plugins.iam.role_ship import lambda_handler

    template["StarbaseAssignedAccount"] = "000000000001"

    with mock.patch("starfleet.worker_ships.plugins.iam.role_ship.LOGGER") as mocked_logger:
        lambda_handler({"Records": [{"body": json.dumps(template)}]}, object())

    # Find the log call we care about:
    for call in mocked_logger.info.call_args_list:
        if call[0][0].startswith("[📝] The following changes"):
            text = call[0][0]
            assert "Resource ID: StarfleetIambicTesting, Update Type: Update, Field: Description" in text
            assert "Resource ID: StarfleetIambicTesting, Update Type: Attach, Field: tags" in text
            assert "pewpewpew" in text
            assert "some_other_key" in text
            assert "Resource ID: arn:aws:iam::aws:policy/ReadOnlyAccess, Update Type: Attach, Field: managed_policies" in text
            assert "arn:aws:iam::aws:policy/ReadOnlyAccess" in text


def test_bad_templates_sync_exceptions(test_index: AccountIndexInstance, template: Dict[str, Any]) -> None:
    """This tests handling the exceptions raised when syncing the role with a bad template."""
    from starfleet.worker_ships.plugins.iam.role_ship import lambda_handler

    template["StarbaseAssignedAccount"] = "000000000001"

    # Test the bad template from the marshmallow iambic validation:
    template["IambicRoleTemplate"]["properties"]["included_accounts"] = "this should not be here"
    with pytest.raises(MarshmallowError) as verr:
        lambda_handler({"Records": [{"body": json.dumps(template)}]}, object())
    assert verr.value.messages[0].startswith("Found forbidden key: included_accounts in the iambic template stanza")
    del template["IambicRoleTemplate"]["properties"]["included_accounts"]

    # Test with a template that makes iambic itself unhappy:
    template["IambicRoleTemplate"]["properties"]["inline_policies"] = [{"effect": "allow", "action": ["", "", ""], "resource": "*"}]
    with pytest.raises(PydanticError) as verr:
        lambda_handler({"Records": [{"body": json.dumps(template)}]}, object())
    assert "value_error.missing" in str(verr)  # policy_name is missing


def test_iambic_exceptions(test_index: AccountIndexInstance, template: Dict[str, Any]) -> None:
    """This tests the handling of exceptions that can result from iambic itself."""
    from starfleet.worker_ships.plugins.iam.role_ship import lambda_handler

    template["StarbaseAssignedAccount"] = "000000000001"

    # First try if the exception is raised:
    with mock.patch("starfleet.worker_ships.plugins.iam.role_ship.LOGGER") as mocked_logger:
        with mock.patch("starfleet.worker_ships.plugins.iam.role_ship.IamRoleWorkerShip.prepare_iambic_template") as mocked_iam:
            mocked_iam._apply_to_account = MagicMock(side_effect=Exception("pewpewpew"))

            with pytest.raises(Exception):
                lambda_handler({"Records": [{"body": json.dumps(template)}]}, object())
        assert mocked_logger.error.call_args[0][0].startswith("[❌] An error occurred when running iambic:")

        mocked_logger.reset_mock()

        # Next, if there are exceptions that are not raised but captured by iambic itself:
        class MockedResult:
            """This is the mocked out iambic result object"""

            exceptions_seen = ["Some Exception", "Some Other Exception"]

        mocked_object = MagicMock()
        # Need to mock out the iambic template to silence a warning about not awaiting things:
        with mock.patch("starfleet.worker_ships.plugins.iam.role_ship.IamRoleWorkerShip.prepare_iambic_template"):
            # Mock out the event loop stuff:
            with mock.patch("asyncio.new_event_loop", return_value=mocked_object):
                mocked_object.run_until_complete = lambda x: MockedResult()
                with pytest.raises(Exception):
                    lambda_handler({"Records": [{"body": json.dumps(template)}]}, object())

        assert mocked_logger.error.call_args[0][0].startswith("[❌] Iambic encountered the following exceptions:")
        assert "Some Exception" in mocked_logger.error.call_args[0][0]
        assert "Some Other Exception" in mocked_logger.error.call_args[0][0]


def test_iambic_logger() -> None:
    """This tests that the IAMbic logger overrider works as expected. This tests all the entry points to the formatter."""
    with mock.patch("starfleet.worker_ships.plugins.iam.iambic_imports.LOGGER") as mocked_logger:
        from iambic.core.logger import log

        some_kwargs = {"some": "value", "some_other": "value"}

        log.debug("some debug message", an="arg", **some_kwargs)
        log.info("some info message", an="arg", **some_kwargs)
        log.error("some error message", an="arg", **some_kwargs)

    mocked_logger.debug.assert_called_once_with("some debug message - logger_kwargs: {'an': 'arg', 'some': 'value', 'some_other': 'value'}")
    mocked_logger.info.assert_called_once_with("some info message - logger_kwargs: {'an': 'arg', 'some': 'value', 'some_other': 'value'}")
    mocked_logger.error.assert_called_once_with("some error message - logger_kwargs: {'an': 'arg', 'some': 'value', 'some_other': 'value'}")
