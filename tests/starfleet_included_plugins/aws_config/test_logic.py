"""Tests for the AWS Config worker's logic

Tests out the logic components of the Config worker

:Module: starfleet.tests.starfleet_included_plugins.aws_config.test_logic
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
# pylint: disable=unused-argument
import os
from typing import Any, Dict
from unittest import mock

import pytest
from botocore.client import BaseClient

from starfleet.account_index.loader import AccountIndexInstance


def test_get_account_region_payload(test_index: AccountIndexInstance, loaded_template: Dict[str, Any]) -> None:
    """This tests that we are able to pull out the proper account/region payload for the given account/region we are running in."""
    from starfleet.worker_ships.plugins.aws_config.logic import DuplicatePayloadError, get_account_region_payload

    # Test a typical account/region that would fit within the DefaultConfiguration:
    payload = get_account_region_payload(loaded_template, "000000000010", "us-east-1")
    assert payload["delivery_channel_details"]["bucket_name"] == "all-bucket"

    # Test pulling out an override:
    payload = get_account_region_payload(loaded_template, "000000000001", "us-west-1")
    assert payload["delivery_channel_details"]["bucket_name"] == "bucket-000000000001"

    # Now test with a duplicate:
    duplicate = dict(loaded_template["account_override_configurations"][0])
    duplicate["include_accounts"]["by_ids"] = []
    duplicate["include_accounts"]["by_names"] = ["Account 1"]
    loaded_template["account_override_configurations"].append(duplicate)
    with pytest.raises(DuplicatePayloadError) as exc:
        get_account_region_payload(loaded_template, "000000000001", "us-west-1")
    assert exc.value.args[0] == loaded_template["account_override_configurations"][2]


def test_get_current_state(aws_config: BaseClient) -> None:
    """This will test the ability to fetch the current state from AWS Config (mocked calls)."""
    from starfleet.worker_ships.plugins.aws_config.logic import get_current_state

    os.environ["MOTO_ACCOUNT_ID"] = "000000000001"  # This prevents oddities with tests as Moto has multi-account support.

    # First, try just fetching the configuration with nothing enabled or defined:
    current_state = get_current_state("000000000001", "us-east-2", "AssumeThisRole", "StarfleetAwsConfig")
    for item in ["ConfigurationRecorder", "RecorderStatus", "DeliveryChannel", "RetentionConfig"]:  # Nothing should be set yet:
        assert not current_state[item]

    # Create a configuration recorder and get the state with it created - this will also have a status of not recording:
    aws_config.put_configuration_recorder(
        ConfigurationRecorder={
            "name": "test",
            "roleARN": "arn:aws:iam::000000000001:role/SomeRole",
            "recordingGroup": {"allSupported": True, "includeGlobalResourceTypes": True},
        }
    )
    confirm_values = {}
    current_state = get_current_state("000000000001", "us-east-2", "AssumeThisRole", "StarfleetAwsConfig")
    # TODO: Need to update this with latest changes made to config API in June 2023!
    assert current_state["ConfigurationRecorder"] == {
        "name": "test",
        "recordingGroup": {"allSupported": True, "includeGlobalResourceTypes": True, "resourceTypes": []},
        "roleARN": "arn:aws:iam::000000000001:role/SomeRole",
    }
    assert current_state["RecorderStatus"] == {"name": "test", "recording": False}
    for item in ["DeliveryChannel", "RetentionConfig"]:
        assert not current_state[item]
    confirm_values["ConfigurationRecorder"] = current_state["ConfigurationRecorder"]

    # Create a delivery channel and get the details for it:
    aws_config.put_delivery_channel(
        DeliveryChannel={
            "name": "test",
            "s3BucketName": "some-bucket",
            "s3KeyPrefix": "some/prefix",
            "s3KmsKeyArn": "arn:aws:kms:us-east-2:000000000001:key/some-key",
            "snsTopicARN": "arn:aws:sns:us-east-2:000000000001:topic/some-topic",
            "configSnapshotDeliveryProperties": {"deliveryFrequency": "One_Hour"},
        }
    )
    current_state = get_current_state("000000000001", "us-east-2", "AssumeThisRole", "StarfleetAwsConfig")
    assert current_state["DeliveryChannel"] == {
        "name": "test",
        "s3BucketName": "some-bucket",
        "s3KeyPrefix": "some/prefix",
        "s3KmsKeyArn": "arn:aws:kms:us-east-2:000000000001:key/some-key",
        "snsTopicARN": "arn:aws:sns:us-east-2:000000000001:topic/some-topic",
        "configSnapshotDeliveryProperties": {"deliveryFrequency": "One_Hour"},
    }
    confirm_values["DeliveryChannel"] = current_state["DeliveryChannel"]
    assert not current_state["RetentionConfig"]

    # Create a retention configuration and get the details for it:
    aws_config.put_retention_configuration(RetentionPeriodInDays=2557)
    current_state = get_current_state("000000000001", "us-east-2", "AssumeThisRole", "StarfleetAwsConfig")
    assert current_state["RetentionConfig"] == {"Name": "default", "RetentionPeriodInDays": 2557}
    confirm_values["RetentionConfig"] = current_state["RetentionConfig"]

    # Start recording:
    aws_config.start_configuration_recorder(ConfigurationRecorderName="test")
    current_state = get_current_state("000000000001", "us-east-2", "AssumeThisRole", "StarfleetAwsConfig")
    assert current_state["RecorderStatus"]["recording"]
    confirm_values["RecorderStatus"] = current_state["RecorderStatus"]

    # Confirm that all the values are what we expect them to be:
    for key, value in confirm_values.items():
        assert current_state[key] == value

    # Clean up:
    del os.environ["MOTO_ACCOUNT_ID"]


def test_make_configuration_recorder_payload(loaded_template: Dict[str, Any]) -> None:
    """This will test out the convenience function for determining if there is work that is needed to be done for the Config Recorder."""
    from starfleet.worker_ships.plugins.aws_config.logic import _make_configuration_recorder_payload

    # We are going to start with empty state:
    working_template = loaded_template["default_configuration"]  # and use some variation of the DefaultConfiguration

    # No state:
    payload = _make_configuration_recorder_payload({}, working_template["recorder_configuration"], "000000000001", "us-east-2")
    assert payload == {
        "name": "default",
        "recordingGroup": {"allSupported": True, "includeGlobalResourceTypes": False, "resourceTypes": []},
        "roleARN": "arn:aws:iam::000000000001:role/MyConfigRole",
    }

    # Pre-existing State -- where it is going to detect no changes being made! The name is different and that's OK!
    current_state = {
        "name": "default",
        "recordingGroup": {"allSupported": True, "includeGlobalResourceTypes": True, "resourceTypes": []},
        "roleARN": "arn:aws:iam::000000000001:role/MyConfigRole",
    }
    assert not _make_configuration_recorder_payload(current_state, working_template["recorder_configuration"], "000000000001", "us-east-1")

    # With a different state -- name should be the same as the state:
    current_state = {
        "name": "default",
        "recordingGroup": {"allSupported": False, "includeGlobalResourceTypes": False, "resourceTypes": ["AWS::EC2::SecurityGroup"]},
        "roleARN": "arn:aws:iam::000000000001:role/MyConfigRole",
    }
    assert _make_configuration_recorder_payload(current_state, working_template["recorder_configuration"], "000000000001", "us-east-1") == {
        "name": "default",
        "recordingGroup": {"allSupported": True, "includeGlobalResourceTypes": True, "resourceTypes": []},
        "roleARN": "arn:aws:iam::000000000001:role/MyConfigRole",
    }

    # With specific resource types supplied (in both state and template):
    current_state = {
        "name": "default",
        "recordingGroup": {"allSupported": False, "includeGlobalResourceTypes": False, "resourceTypes": ["AWS::EC2::SecurityGroup", "AWS::S3::Bucket"]},
        "roleARN": "arn:aws:iam::000000000001:role/MyConfigRole",
    }
    working_template["recorder_configuration"]["recording_group"] = {"resource_types": ["AWS::EC2::SecurityGroup", "AWS::S3::Bucket"]}
    assert not _make_configuration_recorder_payload(current_state, working_template["recorder_configuration"], "000000000001", "us-east-1")


def test_make_delivery_channel_payload(loaded_template: Dict[str, Any]) -> None:
    """This will test out the convenience function for determining if there is work that is needed to be done for the Delivery Channel."""
    from starfleet.worker_ships.plugins.aws_config.logic import _make_delivery_channel_payload

    # No name is defined and no state:
    payload = _make_delivery_channel_payload({}, loaded_template["default_configuration"]["delivery_channel_details"])
    assert payload == {"configSnapshotDeliveryProperties": {"deliveryFrequency": "TwentyFour_Hours"}, "s3BucketName": "all-bucket", "name": "default"}

    # With more details (and a name supplied):
    working_template = loaded_template["account_override_configurations"][0]["delivery_channel_details"]
    payload = _make_delivery_channel_payload({"DeliveryChannel": {}}, working_template)
    assert payload == {
        "s3BucketName": "bucket-000000000001",
        "configSnapshotDeliveryProperties": {"deliveryFrequency": "TwentyFour_Hours"},
        "s3KmsKeyArn": "arn:aws:kms:us-west-1:000000000001:key/1234-1445-1919232",
        "snsTopicARN": "arn:aws:sns:us-west-1:000000000001:topic/sometopic",
        "name": "us-west-1-000000000001",
        "s3KeyPrefix": "some/prefix/",
    }

    # With state that matches:
    current_state = {"configSnapshotDeliveryProperties": {"deliveryFrequency": "TwentyFour_Hours"}, "s3BucketName": "all-bucket", "name": "default"}
    assert not _make_delivery_channel_payload(current_state, loaded_template["default_configuration"]["delivery_channel_details"])


def test_make_retention_config_payload(loaded_template: Dict[str, Any]) -> None:
    """This will test out the convenience function for determining if there is work that is needed to be done for the Retention Configuration."""
    from starfleet.worker_ships.plugins.aws_config.logic import _make_retention_config_payload

    # No state:
    payload = _make_retention_config_payload({}, loaded_template["default_configuration"]["retention_period_in_days"])
    assert payload == {"RetentionPeriodInDays": 2557}

    # With a state that's correct:
    assert not _make_retention_config_payload(
        {"name": "default", "RetentionPeriodInDays": 2557}, loaded_template["default_configuration"]["retention_period_in_days"]
    )

    # With a state that's not correct
    payload = _make_retention_config_payload(
        {"name": "default", "RetentionPeriodInDays": 30}, loaded_template["default_configuration"]["retention_period_in_days"]
    )
    assert payload == {"RetentionPeriodInDays": 2557}


def test_make_recording_payload() -> None:
    """This will test out the convenience function for determining if there is work that is needed to be done for the enabling/disabling recording."""
    from starfleet.worker_ships.plugins.aws_config.logic import _make_recording_payload, RecorderAction

    # No state but enable:
    assert _make_recording_payload({}, True) == RecorderAction.START_RECORDING

    # No state and don't enable:
    assert _make_recording_payload({}, False) == RecorderAction.DO_NOTHING

    # State is enabled and template says to enable:
    assert _make_recording_payload({"name": "default", "recording": True, "lastStatus": "Success"}, True) == RecorderAction.DO_NOTHING

    # State is disabled and template says to enable:
    assert _make_recording_payload({"name": "default", "recording": False, "lastStatus": "Success"}, True) == RecorderAction.START_RECORDING

    # State is enabled and the template says to disable:
    assert _make_recording_payload({"name": "default", "recording": True, "lastStatus": "Success"}, False) == RecorderAction.STOP_RECORDING


def test_determine_workload(loaded_template: Dict[str, Any]) -> None:
    """
    This will test that we get the proper workload figured out.

    We have largely tested all the submodules so this is mostly going to verify that we get the correct full dictionary back out.
    """
    from starfleet.worker_ships.plugins.aws_config.logic import determine_workload, RecorderAction

    # With no state and the DefaultConfiguration, us-east-1:
    current_state = {"ConfigurationRecorder": {}, "DeliveryChannel": {}, "RecorderStatus": {}, "RetentionConfig": {}}
    workload = determine_workload(current_state, loaded_template["default_configuration"], "000000000001", "us-east-1")
    assert workload == {
        "ConfigurationRecorder": {
            "roleARN": "arn:aws:iam::000000000001:role/MyConfigRole",
            "recordingGroup": {"allSupported": True, "includeGlobalResourceTypes": True, "resourceTypes": []},
            "name": "default",
        },
        "DeliveryChannel": {"s3BucketName": "all-bucket", "configSnapshotDeliveryProperties": {"deliveryFrequency": "TwentyFour_Hours"}, "name": "default"},
        "RetentionConfig": {"RetentionPeriodInDays": 2557},
        "EnableRecording": RecorderAction.START_RECORDING,
    }

    # Same as above but for us-east-2:
    workload = determine_workload(current_state, loaded_template["default_configuration"], "000000000001", "us-east-2")
    assert workload["ConfigurationRecorder"] == {
        "roleARN": "arn:aws:iam::000000000001:role/MyConfigRole",
        "recordingGroup": {"allSupported": True, "includeGlobalResourceTypes": False, "resourceTypes": []},
        "name": "default",
    }

    # Not recording and no retention configuration:
    current_state = {
        "ConfigurationRecorder": {
            "roleARN": "arn:aws:iam::000000000001:role/MyConfigRole",
            "recordingGroup": {"allSupported": True, "includeGlobalResourceTypes": True, "resourceTypes": []},
            "name": "default",
        },
        "DeliveryChannel": {"s3BucketName": "all-bucket", "configSnapshotDeliveryProperties": {"deliveryFrequency": "TwentyFour_Hours"}, "name": "default"},
        "RetentionConfig": {},
        "RecorderStatus": {},
    }
    workload = determine_workload(current_state, loaded_template["default_configuration"], "000000000001", "us-east-1")
    assert workload == {
        "ConfigurationRecorder": {},
        "DeliveryChannel": {},
        "EnableRecording": RecorderAction.START_RECORDING,
        "RetentionConfig": {"RetentionPeriodInDays": 2557},
    }


def test_log_summary(loaded_template: Dict[str, Any]) -> None:
    """This tests out the summary logging."""
    from starfleet.worker_ships.plugins.aws_config.logic import determine_workload, _log_summary, RecorderAction

    # We will start with everything being wrong and then test each section being corrected.
    current_state = {"ConfigurationRecorder": {}, "DeliveryChannel": {}, "RecorderStatus": {}, "RetentionConfig": {}}
    workload = determine_workload(current_state, loaded_template["default_configuration"], "000000000001", "us-east-1")

    with mock.patch("starfleet.worker_ships.plugins.aws_config.logic.LOGGER") as mocked_logger:
        # Everything is wrong:
        logs_should_be = [
            "[🙅‍♂️] Configuration Recorder",
            "[🙅‍♂️] Delivery Channel",
            "[🙅‍♂️] Retention Configuration",
            "[🙅‍♂️] The recorder needs to be enabled",
        ]
        assert _log_summary(workload)
        for index, value in enumerate(logs_should_be):
            assert value in mocked_logger.info.call_args_list[index][0][0]
        mocked_logger.reset_mock()  # Always reset after each section.

        # Recorder fixed:
        logs_should_be[0] = "[🆗] Configuration Recorder"
        workload["ConfigurationRecorder"] = {}
        assert _log_summary(workload)
        for index, value in enumerate(logs_should_be):
            assert value in mocked_logger.info.call_args_list[index][0][0]
        mocked_logger.reset_mock()

        # Delivery Channel Fixed
        logs_should_be[1] = "[🆗] Delivery Channel"
        workload["DeliveryChannel"] = {}
        assert _log_summary(workload)
        for index, value in enumerate(logs_should_be):
            assert value in mocked_logger.info.call_args_list[index][0][0]
        mocked_logger.reset_mock()

        # Retention Configuration Fixed
        logs_should_be[2] = "[🆗] Retention Configuration"
        workload["RetentionConfig"] = {}
        assert _log_summary(workload)
        for index, value in enumerate(logs_should_be):
            assert value in mocked_logger.info.call_args_list[index][0][0]
        mocked_logger.reset_mock()

        # Make it so that the recorder needs to stopped:
        workload["EnableRecording"] = RecorderAction.STOP_RECORDING
        logs_should_be[3] = "[🙅‍♂️] The recorder needs to be disabled"
        assert _log_summary(workload)
        for index, value in enumerate(logs_should_be):
            assert value in mocked_logger.info.call_args_list[index][0][0]
        mocked_logger.reset_mock()

        # Recorder status is fixed:
        workload["EnableRecording"] = RecorderAction.DO_NOTHING
        logs_should_be[3] = "[🆗] The recorder's status is in sync"
        assert not _log_summary(workload)
        for index, value in enumerate(logs_should_be):
            assert value in mocked_logger.info.call_args_list[index][0][0]
        mocked_logger.reset_mock()


def test_sync_config(loaded_template: Dict[str, Any], aws_config: BaseClient) -> None:
    """This tests out syncing config to AWS."""
    from starfleet.worker_ships.plugins.aws_config.logic import determine_workload, get_current_state, sync_config, RecorderAction

    with mock.patch("starfleet.worker_ships.plugins.aws_config.logic.LOGGER") as mocked_logger:
        # First test with nothing to do:
        workload = {"ConfigurationRecorder": {}, "DeliveryChannel": {}, "EnableRecording": RecorderAction.DO_NOTHING, "RetentionConfig": {}}
        alert_text = sync_config(workload, {}, "000000000001", "us-east-1", "AssumeThisRole", "StarfleetAwsConfig", False)
        # It will be the last logged item:
        assert (
            mocked_logger.info.call_args_list[len(mocked_logger.call_args_list) - 1][0][0]
            == "[✅] Nothing to do. Everything is all set in 000000000001/us-east-1."
        )
        assert not alert_text
        mocked_logger.reset_mock()

        # Then test with work but with commit disabled:
        current_state = {"ConfigurationRecorder": {}, "DeliveryChannel": {}, "RecorderStatus": {}, "RetentionConfig": {}}
        workload = determine_workload(current_state, loaded_template["default_configuration"], "000000000001", "us-east-1")
        alert_text = sync_config(workload, loaded_template["default_configuration"], "000000000001", "us-east-1", "AssumeThisRole", "StarfleetAwsConfig", False)
        assert (
            mocked_logger.info.call_args_list[len(mocked_logger.call_args_list) - 1][0][0]
            == "[⏭️] There is work to do but because commit is disabled, no action is being taken in 000000000001/us-east-1."
        )
        assert not alert_text
        mocked_logger.reset_mock()

    # Commit is enabled... Let's gooooooo
    alert_text = sync_config(workload, loaded_template["default_configuration"], "000000000001", "us-east-1", "AssumeThisRole", "StarfleetAwsConfig", True)

    # Verify that everything is all good by using our existing get_current_state function:
    current_state = get_current_state("000000000001", "us-east-1", "AssumeThisRole", "StarfleetAwsConfig")
    workload = determine_workload(current_state, loaded_template["default_configuration"], "000000000001", "us-east-1")
    assert workload == {"ConfigurationRecorder": {}, "DeliveryChannel": {}, "EnableRecording": RecorderAction.DO_NOTHING, "RetentionConfig": {}}
    assert (
        alert_text
        == "> ✅  Updated the Configuration Recorder\n> ✅  Updated the Delivery Channel\n> ✅  Updated the Retention Configuration\n"
        + "> ✅  Started the Configuration Recorder\n\n\nCheck out the Lambda logs for more verbose details."
    )

    # Let's try stopping the recorder (this also tests out what happens if the other fields are false):
    workload["EnableRecording"] = RecorderAction.STOP_RECORDING
    alert_text = sync_config(workload, loaded_template["default_configuration"], "000000000001", "us-east-1", "AssumeThisRole", "StarfleetAwsConfig", True)
    assert not get_current_state("000000000001", "us-east-1", "AssumeThisRole", "StarfleetAwsConfig")["RecorderStatus"]["recording"]
    assert alert_text == "> ✅  Stopped the Configuration Recorder\n\n\nCheck out the Lambda logs for more verbose details."
