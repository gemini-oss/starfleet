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
from unittest.mock import MagicMock

import pytest
from botocore.client import BaseClient

from starfleet.worker_ships.loader import StarfleetWorkerShipLoader


def test_process_eventbridge_timed_events(
    aws_s3: BaseClient,
    aws_sqs: BaseClient,
    payload_templates: Set[str],
    template_bucket: str,
    fanout_queue: str,
    timed_event: Dict[str, Any],
    worker_ships: MagicMock,
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
    payload_templates: Set[str],
    test_worker_ship_loader: StarfleetWorkerShipLoader,
    test_configuration: Dict[str, Any],
    worker_queue: str,
    worker_ships: MagicMock,
) -> None:
    """Tests that we can properly fan out the payload to single invocation workers."""
    from starfleet.starbase.entrypoints import fanout_payload_lambda_handler

    fanout_payload_lambda_handler(fanout_lambda_payload, object())

    # Confirm that the queue got the correct payload:
    messages = aws_sqs.receive_message(QueueUrl=worker_queue, MaxNumberOfMessages=10).get("Messages")
    worker = test_worker_ship_loader.get_worker_ships()["TestingStarfleetWorkerPlugin"]
    worker.load_template(json.loads(messages[0]["Body"]))
    assert worker.payload["template_name"] == "TestWorkerTemplate"

    with mock.patch("starfleet.starbase.main.LOGGER") as mocked_logger:
        # TODO: Remove this when we add more invocation types:
        test_configuration["TestingStarfleetWorkerPlugin"]["FanOutStrategy"] = "ACCOUNT"
        fanout_payload_lambda_handler(fanout_lambda_payload, object())
        assert mocked_logger.warning.call_args.args[0] == "[🚧] Fan Out Strategy: ACCOUNT is not implemented yet!"


def test_fan_out_invalid_worker(worker_ships: MagicMock) -> None:
    """This tests that an invalid worker specified in the template throws the proper error back out."""
    from starfleet.starbase.main import fan_out_payload, NoShipPluginError

    with pytest.raises(NoShipPluginError):
        fan_out_payload({"worker_ship": "fake", "template_prefix": "fake"})


def test_fan_out_invalid_template(worker_ships: MagicMock) -> None:
    """Tests what happens when an invalid template is loaded by the fan out Lambda execution."""
    from starfleet.starbase.main import fan_out_payload, ValidationError

    with mock.patch("starfleet.starbase.main.fetch_template", lambda *args: {"not": "conformant with schema"}):
        with pytest.raises(ValidationError) as verr:
            fan_out_payload({"worker_ship": "TestingStarfleetWorkerPlugin", "template_prefix": "fake"})

    assert "TemplateDescription" in verr.value.messages
    assert "TemplateName" in verr.value.messages


def test_multiple_records_warning_fanout() -> None:
    """This just tests that the warning is emitted if there are multiple records in the event to the Lambda function."""
    from starfleet.starbase.entrypoints import fanout_payload_lambda_handler

    with mock.patch("starfleet.starbase.entrypoints.fan_out_payload"):
        with mock.patch("starfleet.starbase.entrypoints.LOGGER") as mocked_logger:
            fanout_payload_lambda_handler({"Records": [{"body": "1"}, {"body": "2"}]}, object())

    assert mocked_logger.error.call_args.args[0].startswith("[🚨] Received more than 1 event for fan out!")
