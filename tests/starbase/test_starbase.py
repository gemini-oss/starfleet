"""Tests for Starfleet's Starbase

This tests the logic for the Starbase

:Module: starfleet.tests.starbase.test_starbase
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
# pylint: disable=unused-argument
import json

from typing import Set, Any, Dict
from unittest import mock

import boto3
import pytest
from botocore.client import BaseClient

from starfleet.account_index.schematics import AccountIndexInstance
from starfleet.worker_ships.loader import StarfleetWorkerShipLoader


def test_process_eventbridge_timed_events(
    aws_s3: BaseClient,
    aws_sqs: BaseClient,
    single_payload_templates: Set[str],
    template_bucket: str,
    fanout_queue: str,
    timed_event: Dict[str, Any],
    worker_ships: StarfleetWorkerShipLoader,
) -> None:
    """This tests the full EventBridge timed events tasking."""
    from starfleet.starbase.entrypoints import eventbridge_timed_lambda_handler

    eventbridge_timed_lambda_handler(timed_event, object())

    # Verify that the SQS queue has all the items in it that are supposed to be there:
    messages = aws_sqs.receive_message(QueueUrl=fanout_queue, MaxNumberOfMessages=10)["Messages"]
    assert len(messages) == 4
    missing_messages = {
        "TestingStarfleetWorkerPlugin:TestingStarfleetWorkerPlugin/template1.yaml",
        "TestingStarfleetWorkerPlugin:TestingStarfleetWorkerPlugin/template2.yaml",
        "TestingStarfleetWorkerPluginTwo:TestingStarfleetWorkerPluginTwo/template1.yaml",
        "TestingStarfleetWorkerPluginTwo:TestingStarfleetWorkerPluginTwo/template2.yaml",
    }
    for msg in messages:
        body = json.loads(msg["Body"])
        missing_messages.remove(f"{body['worker_ship']}:{body['template_prefix']}")

        # Also, clear out the SQS queue so we can do more tests:
        aws_sqs.delete_message(QueueUrl=fanout_queue, ReceiptHandle=msg["ReceiptHandle"])

    assert not missing_messages  # All messages should be accounted for.

    # Try an event that doesn't correspond with any of the timed workers (TWELVE_HOURLY)
    timed_event["name"] = "TWELVE_HOURLY"
    with mock.patch("starfleet.starbase.main.LOGGER") as mocked_logger:
        eventbridge_timed_lambda_handler(timed_event, object())
    assert mocked_logger.info.call_args.args[0] == "[🌑] No ships to task for the timed event: TWELVE_HOURLY."
    assert not aws_sqs.receive_message(QueueUrl=fanout_queue, MaxNumberOfMessages=10).get("Messages")

    # Now, let's try clearing out the templates in S3. This should result in nothing being placed in SQS:
    # Do this by deleting the objects:
    delete_objects = [
        "TestingStarfleetWorkerPlugin/template1.yaml",
        "TestingStarfleetWorkerPlugin/template2.yaml",
        "TestingStarfleetWorkerPluginTwo/template1.yaml",
        "TestingStarfleetWorkerPluginTwo/template2.yaml",
    ]
    aws_s3.delete_objects(Bucket=template_bucket, Delete={"Objects": [{"Key": key} for key in delete_objects]})
    timed_event["name"] = "HOURLY"

    with mock.patch("starfleet.starbase.main.LOGGER") as mocked_logger:
        eventbridge_timed_lambda_handler(timed_event, object())
    for call in mocked_logger.warning.call_args_list:
        assert call.args[0].startswith("[⚠️] No templates found for worker ship:")

    # Should be nothing placed on SQS:
    assert not aws_sqs.receive_message(QueueUrl=fanout_queue, MaxNumberOfMessages=10).get("Messages")


def test_fan_out_single_invocation(
    aws_s3: BaseClient,
    aws_sqs: BaseClient,
    fanout_lambda_payload: Dict[str, Any],
    template_bucket: str,
    single_payload_templates: Set[str],
    test_configuration: Dict[str, Any],
    worker_queue: str,
    worker_ships: StarfleetWorkerShipLoader,
    test_index: AccountIndexInstance,
) -> None:
    """Tests that we can properly fan out the payload to single invocation workers."""
    from starfleet.starbase.entrypoints import fanout_payload_lambda_handler

    fanout_payload_lambda_handler(fanout_lambda_payload, object())

    # Confirm that the queue got the correct payload:
    messages = aws_sqs.receive_message(QueueUrl=worker_queue, MaxNumberOfMessages=10, WaitTimeSeconds=0).get("Messages")
    worker = worker_ships.get_worker_ships()["TestingStarfleetWorkerPlugin"]
    worker.load_template(json.loads(messages[0]["Body"]))
    assert worker.payload["template_name"] == "TestWorkerTemplate"


def test_fan_out_account(
    aws_s3: BaseClient,
    aws_sqs: BaseClient,
    fanout_lambda_payload: Dict[str, Any],
    template_bucket: str,
    account_payload_templates: Set[str],
    test_configuration: Dict[str, Any],
    worker_queue: str,
    account_worker_ships: StarfleetWorkerShipLoader,
    test_index: AccountIndexInstance,
) -> None:
    """Tests that we can properly fan out the payload for account workers. This also tests the utility function."""
    from starfleet.starbase.entrypoints import fanout_payload_lambda_handler

    fanout_payload_lambda_handler(fanout_lambda_payload, object())

    # Confirm that the queue got the correct payload:
    all_messages = []
    while True:
        messages = aws_sqs.receive_message(QueueUrl=worker_queue, MaxNumberOfMessages=10).get("Messages")
        if not messages:
            break

        all_messages += messages

    # There should be 18 messages, because we tasked 18 accounts [20 accounts - the org root (not explicitly set to run on) - Account 1 = 18 accounts total tasked]
    assert len(all_messages) == 18

    # Iterate through and verify that everything is correct. Also verify and confirm that we are not tasking the org root (Account 20), and Account 1 which is explicitly
    # excluded in the template by name:
    worker = account_worker_ships.get_worker_ships()["TestingStarfleetWorkerPlugin"]
    all_accounts = test_index.get_all_accounts()
    for message in all_messages:
        worker.load_template(json.loads(message["Body"]))
        # Remove the seen accounts. If not found, this will raise an exception. At the end only 2 accounts should remain (20, and 1) which are excluded:
        all_accounts.remove(worker.payload["starbase_assigned_account"])
        assert worker.payload["template_name"] == "TestWorkerTemplate"

    assert all_accounts == {"000000000001", "000000000020"}  # The remaining accounts that weren't tasked


def test_account_fanout_nothing_to_task(test_index: AccountIndexInstance) -> None:
    """This tests that we log out that we have no accounts to task if the template fails to resolve to any actual accounts."""
    from starfleet.starbase.utils import account_fanout
    from starfleet.worker_ships.base_payload_schemas import BaseAccountPayloadTemplate

    template = {
        "include_accounts": {"all_accounts": False, "by_names": ["fake_account"], "by_ids": ["fake_account"], "by_tags": [], "by_org_units": []},
        "exclude_accounts": {},
        "operate_in_org_root": False,
    }

    with mock.patch("starfleet.starbase.utils.LOGGER") as mocked_logger:
        account_fanout(template, BaseAccountPayloadTemplate(), "", "", "", boto3.client("sqs", region_name="us-east-1"), "fake_ship")

    assert "has no accounts to task" in mocked_logger.error.call_args[0][0]


def test_account_region_fanout_nothing_to_task(test_index: AccountIndexInstance) -> None:
    """This tests that we log out that we have no accounts/regions to task if the template fails to resolve to any actual account/region pairs."""
    from starfleet.starbase.utils import account_region_fanout
    from starfleet.worker_ships.base_payload_schemas import BaseAccountRegionPayloadTemplate

    # Include and exclude regions are the same:
    template = {
        "include_accounts": {"all_accounts": True, "by_names": [], "by_ids": [], "by_tags": [], "by_org_units": []},
        "exclude_accounts": {},
        "operate_in_org_root": True,
        "include_regions": set("us-east-1"),
        "exclude_regions": set("us-east-1"),
    }
    with mock.patch("starfleet.starbase.utils.LOGGER") as mocked_logger:
        account_region_fanout(template, BaseAccountRegionPayloadTemplate(), "", "", "", boto3.client("sqs", region_name="us-east-1"), "fake_ship")
    assert "has no accounts/regions to task" in mocked_logger.error.call_args[0][0]

    # And with no accounts, but regions:
    template = {
        "include_accounts": {"all_accounts": False, "by_names": ["fake_account"], "by_ids": [], "by_tags": [], "by_org_units": []},
        "exclude_accounts": {},
        "operate_in_org_root": True,
        "include_regions": set("us-east-1"),
        "exclude_regions": [],
    }
    with mock.patch("starfleet.starbase.utils.LOGGER") as mocked_logger:
        account_region_fanout(template, BaseAccountRegionPayloadTemplate(), "", "", "", boto3.client("sqs", region_name="us-east-1"), "fake_ship")
    assert "has no accounts/regions to task" in mocked_logger.error.call_args[0][0]


def test_account_fanout_wrong_subclass(
    fanout_lambda_payload: Dict[str, Any],
    template_bucket: str,
    single_payload_templates: Set[str],
    test_index: AccountIndexInstance,
    aws_s3: BaseClient,
    worker_ships: StarfleetWorkerShipLoader,
) -> None:
    """This tests that we check if we have an Account worker with a template that doesn't properly subclass the BaseAccountPayloadTemplate class."""
    from starfleet.starbase.entrypoints import fanout_payload_lambda_handler
    from starfleet.starbase.main import InvalidTemplateForFanoutError
    from starfleet.worker_ships.ship_schematics import FanOutStrategy

    # Update the worker class configuration to be an ACCOUNT worker:
    ship = worker_ships.get_worker_ships()["TestingStarfleetWorkerPlugin"]
    ship.fan_out_strategy = FanOutStrategy.ACCOUNT
    with pytest.raises(InvalidTemplateForFanoutError):
        fanout_payload_lambda_handler(fanout_lambda_payload, object())

    # Update the worker class configuration to be an ACCOUNT_REGION worker:
    ship = worker_ships.get_worker_ships()["TestingStarfleetWorkerPlugin"]
    ship.fan_out_strategy = FanOutStrategy.ACCOUNT_REGION
    with pytest.raises(InvalidTemplateForFanoutError):
        fanout_payload_lambda_handler(fanout_lambda_payload, object())


def test_fan_out_invalid_worker(worker_ships: StarfleetWorkerShipLoader) -> None:
    """This tests that an invalid worker specified in the template throws the proper error back out."""
    from starfleet.starbase.main import fan_out_payload, NoShipPluginError

    with pytest.raises(NoShipPluginError):
        fan_out_payload({"worker_ship": "fake", "template_prefix": "fake"})


def test_fan_out_invalid_template(worker_ships: StarfleetWorkerShipLoader) -> None:
    """Tests what happens when an invalid template is loaded by the fan out Lambda execution."""
    from starfleet.starbase.main import fan_out_payload, ValidationError

    with mock.patch("starfleet.starbase.main.fetch_template", lambda *args: {"not": "conformant with schema"}):
        with pytest.raises(ValidationError) as verr:
            fan_out_payload({"worker_ship": "TestingStarfleetWorkerPlugin", "template_prefix": "fake"})

    assert "TemplateDescription" in verr.value.messages
    assert "TemplateName" in verr.value.messages


def test_multiple_records_warning_fanout(test_index: AccountIndexInstance) -> None:
    """This just tests that the warning is emitted if there are multiple records in the event to the Lambda function."""
    from starfleet.starbase.entrypoints import fanout_payload_lambda_handler

    with mock.patch("starfleet.starbase.entrypoints.fan_out_payload"):
        with mock.patch("starfleet.starbase.entrypoints.LOGGER") as mocked_logger:
            fanout_payload_lambda_handler({"Records": [{"body": "1"}, {"body": "2"}]}, object())

    assert mocked_logger.error.call_args.args[0].startswith("[🚨] Received more than 1 event for fan out!")


# pylint: disable=too-many-locals
def test_fan_out_account_regions(
    aws_s3: BaseClient,
    aws_sqs: BaseClient,
    fanout_lambda_payload: Dict[str, Any],
    template_bucket: str,
    account_region_payload_templates: Set[str],
    test_configuration: Dict[str, Any],
    worker_queue: str,
    account_region_worker_ships: StarfleetWorkerShipLoader,
    test_index: AccountIndexInstance,
) -> None:
    """Tests that we can properly fan out the payload for account/region workers. This also tests the utility function."""
    from starfleet.starbase.entrypoints import fanout_payload_lambda_handler

    fanout_payload_lambda_handler(fanout_lambda_payload, object())

    # Confirm that the queue got the correct payload:
    all_messages = []
    while True:
        messages = aws_sqs.receive_message(QueueUrl=worker_queue, MaxNumberOfMessages=10, WaitTimeSeconds=0).get("Messages")
        if not messages:
            break

        all_messages += messages

    # There should be 18 messages, because we tasked 16 account/regions
    # [5 accounts - Account 1 = 4 accounts total tasked * (5 regions - 1 excluded = 4 regions) ==> 4 * 4 = 16 tasks]
    assert len(all_messages) == 16

    # Iterate through and verify that everything is correct. Also verify and confirm that we are not tasking the org root (Account 20), and Account 1 which is explicitly
    # excluded in the template by name:
    worker = account_region_worker_ships.get_worker_ships()["TestingStarfleetWorkerPlugin"]
    all_accounts_regions = test_index.get_accounts_by_regions({"us-west-1", "us-east-1", "us-east-2", "eu-west-1", "ca-central-1"})
    for message in all_messages:
        worker.load_template(json.loads(message["Body"]))
        # Remove the seen account/regions. If not found, this will raise an exception.
        # At the end only 2 accounts should remain (20, and 1) which are excluded and 1 region (us-west-1):
        all_accounts_regions[worker.payload["starbase_assigned_region"]].remove(worker.payload["starbase_assigned_account"])
        assert worker.payload["template_name"] == "TestWorkerTemplate"

    assert all_accounts_regions.pop("us-west-1") == test_index.get_all_accounts()  # us-west-1 wasn't tasked
    for region in ["us-east-1", "us-east-2", "eu-west-1", "ca-central-1"]:
        # Verify that for the remaining regions, we have tasked the accounts in those regions. If we did, then we removed the account
        # from the set. So the intersection of the accounts we were supposed to task with the region map is empty.
        assert not all_accounts_regions.pop(region).intersection({"000000000002", "000000000003", "000000000004", "000000000005"})
    assert not all_accounts_regions  # nothing should be remaining, which means we have fully verified everything
