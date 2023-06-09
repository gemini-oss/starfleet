"""AWS Config enablement logic

This is where all the logic exists for the Config worker.

:Module: starfleet.worker_ships.plugins.aws_config.logic
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
from enum import Enum
from typing import Any, Dict

from botocore.client import BaseClient
from cloudaux import sts_conn
from retry import retry

from starfleet.account_index.resolvers import resolve_worker_template_account_regions
from starfleet.utils.logging import LOGGER


class DuplicatePayloadError(Exception):
    """Raised if an account/region matches multiple override configurations."""


class RecorderAction(Enum):
    """Enum to describe what we need to do with the recorder."""

    DO_NOTHING = 1
    START_RECORDING = 2
    STOP_RECORDING = 3


def get_account_region_payload(payload: Dict[str, Any], account: str, region: str) -> Dict[str, Any]:
    """
    This will look at the payload and figure out which payload component to pull out.
    This will:
        1. Verify if this account/region has an override configuration
        2. Verify that there aren't more than 1 override configurations that this payload applies to (it can only apply to 1)
        3. If we are not able to locate an override, then this will just return the DefaultConfiguration part out of the template.

    This has a hard dependency on Starfleet configured Account Index.
    """
    # Check for overrides:
    payload_portion = None
    for override in payload["account_override_configurations"]:
        override_account_regions = resolve_worker_template_account_regions(override, org_root_check=False)

        # Did we find the override?
        if account in override_account_regions and region in override_account_regions[account]:
            # Have we _already_ found this override? If this overlaps, and we need to raise an error:
            if payload_portion:
                LOGGER.error(f"[🔥] This account/region: {account}/{region} has more than 1 override defined: {override}. Can't continue!")
                raise DuplicatePayloadError(override)

            LOGGER.debug(f"[🔀] We found an override configuration in the payload for: {account}/{region}. It is: {override}")
            payload_portion = override

    # If we didn't find an override, then we just need to get the DefaultConfiguration:
    if not payload_portion:
        payload_portion = payload["default_configuration"]
        LOGGER.debug(f"[ℹ️] No override found so using the configuration for all accounts and regions: {payload_portion}")

    return payload_portion


@sts_conn("config")
def describe_delivery_channels(client: BaseClient, **kwargs) -> Dict[str, Any]:
    """CloudAux wrapped call for getting the delivery channels."""
    recorders = client.describe_delivery_channels(**kwargs)

    if recorders.get("DeliveryChannels", []):
        return recorders["DeliveryChannels"][0]

    return {}


@sts_conn("config")
def describe_configuration_recorders(client: BaseClient, **kwargs) -> Dict[str, Any]:
    """CloudAux wrapped call for getting the configuration recorders."""
    recorders = client.describe_configuration_recorders(**kwargs)

    if recorders.get("ConfigurationRecorders", []):
        return recorders["ConfigurationRecorders"][0]

    return {}


@sts_conn("config")
def describe_retention_configurations(client: BaseClient, **kwargs) -> Dict[str, Any]:
    """CloudAux wrapped call for getting the retention configurations."""
    recorders = client.describe_retention_configurations(**kwargs)

    if recorders.get("RetentionConfigurations", []):
        return recorders["RetentionConfigurations"][0]

    return {}


@sts_conn("config")
def describe_configuration_recorder_status(client: BaseClient, **kwargs) -> Dict[str, Any]:
    """CloudAux wrapped call for getting the recorder status."""
    recorders = client.describe_configuration_recorder_status(**kwargs)

    if recorders.get("ConfigurationRecordersStatus", []):
        return recorders["ConfigurationRecordersStatus"][0]

    return {}


@retry(tries=3, jitter=(0, 3), delay=1, backoff=2, max_delay=3, logger=LOGGER)
@sts_conn("config")
def put_configuration_recorder(**kwargs) -> None:
    """CloudAux wrapped call for setting the Configuration Recorder."""
    kwargs.pop("client").put_configuration_recorder(**kwargs)


@retry(tries=3, jitter=(0, 3), delay=1, backoff=2, max_delay=3, logger=LOGGER)
@sts_conn("config")
def put_delivery_channel(**kwargs) -> None:
    """CloudAux wrapped call for setting the Delivery Channel."""
    kwargs.pop("client").put_delivery_channel(**kwargs)


@retry(tries=3, jitter=(0, 3), delay=1, backoff=2, max_delay=3, logger=LOGGER)
@sts_conn("config")
def put_retention_configuration(**kwargs) -> None:
    """CloudAux wrapped call for setting the Retention Configuration."""
    kwargs.pop("client").put_retention_configuration(**kwargs)


@retry(tries=3, jitter=(0, 3), delay=1, backoff=2, max_delay=3, logger=LOGGER)
@sts_conn("config")
def start_configuration_recorder(**kwargs) -> None:
    """CloudAux wrapped call for starting the configuration recorder."""
    kwargs.pop("client").start_configuration_recorder(**kwargs)


@retry(tries=3, jitter=(0, 3), delay=1, backoff=2, max_delay=3, logger=LOGGER)
@sts_conn("config")
def stop_configuration_recorder(**kwargs) -> None:
    """CloudAux wrapped call for stopping the configuration recorder."""
    kwargs.pop("client").stop_configuration_recorder(**kwargs)


# pylint: disable=no-value-for-parameter
def get_current_state(account: str, region: str, assume_role: str, session_name: str) -> Dict[str, Any]:
    """
    This will obtain the current state of AWS Config in the account/region and return a dictionary that contains the configuration details.

    That dictionary looks like this:
    {
        "ConfigurationRecorder": {...},
        "DeliveryChannel": {...},
        "RecorderStatus": {...},
        "RetentionConfig": {...}
    }

    *Note*: AWS Config only supports having 1 Configuration Recorder, Delivery Channel, and Retention Configuration per account/region -- even though these are paginated
    API calls that return lists. We are going to make an assumption that we will at most receive 1 object and use that 1 object if found.
    """
    current_state = {}

    LOGGER.debug("[📼] Fetching the configuration recorder...")
    current_state["ConfigurationRecorder"] = describe_configuration_recorders(
        account_number=account,
        region=region,
        assume_role=assume_role,
        session_name=session_name,
        sts_client_kwargs={"endpoint_url": f"https://sts.{region}.amazonaws.com", "region_name": region},
    )

    # We only care about specific keys in the current state (this prevents changes to the Config API causing our comparison logic
    # to fail):
    if recording_group := current_state["ConfigurationRecorder"].get("recordingGroup"):
        cleaned_up_current_state = {}
        current_state_keys = {"allSupported", "includeGlobalResourceTypes", "resourceTypes"}

        for key in recording_group.keys():
            if key in current_state_keys:
                cleaned_up_current_state[key] = recording_group[key]

        current_state["ConfigurationRecorder"]["recordingGroup"] = cleaned_up_current_state

    LOGGER.debug("[⏺️] Fetching the current recorder status...")
    current_state["RecorderStatus"] = describe_configuration_recorder_status(
        account_number=account,
        region=region,
        assume_role=assume_role,
        session_name=session_name,
        sts_client_kwargs={"endpoint_url": f"https://sts.{region}.amazonaws.com", "region_name": region},
    )

    LOGGER.debug("[🚚] Fetching the delivery channel...")
    current_state["DeliveryChannel"] = describe_delivery_channels(
        account_number=account,
        region=region,
        assume_role=assume_role,
        session_name=session_name,
        sts_client_kwargs={"endpoint_url": f"https://sts.{region}.amazonaws.com", "region_name": region},
    )

    LOGGER.debug("[🗄️] Fetching the retention configuration...")
    current_state["RetentionConfig"] = describe_retention_configurations(
        account_number=account,
        region=region,
        assume_role=assume_role,
        session_name=session_name,
        sts_client_kwargs={"endpoint_url": f"https://sts.{region}.amazonaws.com", "region_name": region},
    )

    return current_state


def _make_configuration_recorder_payload(current_state: Dict[str, Any], template: Dict[str, Any], account: str, region: str) -> Dict[str, Any]:
    """
    This is a convenience function to pull out the configuration recorder details that needs to be set in AWS.

    The name of the config recorder is special. This is really an optional field. It will follow this logic:
    1. If there is no config recorder, then use PreferredName in the template (defaults to "default")
    2. If there is a config recorder, then we will simply use the existing value of the recorder
    ^^ This is the case because we can't replace the name, and the only way to do it is to delete and re-create.
    We are not going to delete and re-create: we are just going to update the existing recorder if found and optimistically
    rename it if we need to create a new one.
    """
    # Figure out what the payload should look like:
    all_supported = template["recording_group"]["resource_types"][0] == "ALL"
    include_global_resource_types = all_supported and region in template["recording_group"].get("globals_in_regions", [])
    payload_dict = {
        "roleARN": f"arn:aws:iam::{account}:role/{template['config_role_name']}",
        "recordingGroup": {"allSupported": all_supported, "includeGlobalResourceTypes": include_global_resource_types},
    }
    if not all_supported:
        payload_dict["recordingGroup"]["resourceTypes"] = template["recording_group"]["resource_types"]
    else:
        payload_dict["recordingGroup"]["resourceTypes"] = []

    # Name logic:
    if current_state.get("name"):  # If we already have a Config recorder, then use its name
        payload_dict["name"] = current_state["name"]
    else:
        payload_dict["name"] = template["preferred_name"]

    # Now that we have what the payload should look like we can compare it. Return an empty dict if they are the same (no work to do)
    if current_state == payload_dict:
        return {}

    # They are in fact out of sync, so return the payload dict out which will be used to inform the next actions.
    return payload_dict


def _make_delivery_channel_payload(current_state: Dict[str, Any], template: Dict[str, Any]) -> Dict[str, Any]:
    """
    This is a convenience function to pull out the delivery channel details that needs to be set in AWS.

    The name of the delivery channel is special. This is really an optional field. It will follow this logic:
    1. If there is no delivery channel, then use PreferredName in the template (defaults to "default")
    2. If there is a delivery channel, then we will simply use the existing value of the delivery channel
    ^^ This is the case because we can't replace the name, and the only way to do it is to delete and re-create.
    We are not going to delete and re-create: we are just going to update the existing delivery channel if found and optimistically
    rename it if we need to create a new one.
    """
    # Figure out what the payload should look like:
    payload_dict = {"s3BucketName": template["bucket_name"], "configSnapshotDeliveryProperties": {"deliveryFrequency": template["s3_delivery_frequency"].value}}
    if template.get("bucket_key_prefix"):
        payload_dict["s3KeyPrefix"] = template["bucket_key_prefix"]
    if template.get("s3_kms_key_arn"):
        payload_dict["s3KmsKeyArn"] = template["s3_kms_key_arn"]
    if template.get("sns_topic_arn"):
        payload_dict["snsTopicARN"] = template["sns_topic_arn"]

    # Name logic:
    if current_state.get("name"):  # If we already have a delivery channel, then use its name
        payload_dict["name"] = current_state["name"]
    elif template.get("preferred_name"):  # If we don't, then use the name in the template (if one is supplied)
        payload_dict["name"] = template["preferred_name"]
    # If we don't have a delivery channel and don't have one specified in the template, then don't include it

    # Now that we have what the payload should look like we can compare it. Return an empty dict if they are the same (no work to do)
    if current_state == payload_dict:
        return {}

    # They are in fact out of sync, so return the payload dict out which will be used to inform the next actions.
    return payload_dict


def _make_retention_config_payload(current_state: Dict[str, Any], retention_period: int) -> Dict[str, int]:
    """
    This is a convenience function to pull out the retention configuration that needs to be set in AWS.

    Retention configuration only needs to set the `RetentionPeriodInDays`. This will only return a payload that has that set
    if what's set is not the same as the template.
    """
    if current_state.get("RetentionPeriodInDays", 0) == retention_period:
        return {}

    return {"RetentionPeriodInDays": retention_period}


def _make_recording_payload(current_state: Dict[str, Any], recording_enabled: bool) -> RecorderAction:
    """
    This is a convenience function that determines if we need to (or don't need to) enable/disable recording.

    This will return a RecorderAction Enum describing on what needs to be done.
    """
    # We lack a retention configuration currently:
    if not current_state:
        # If the template does NOT have recording enabled, then there is nothing to do because we are not recording:
        if not recording_enabled:
            return RecorderAction.DO_NOTHING

        # If the template has recording enabled, then we need to turn it on because it's not currently set:
        return RecorderAction.START_RECORDING

    # We have a retention configuration. If the recording state is the same as our template, then nothing to do:
    if current_state.get("recording", False) == recording_enabled:
        return RecorderAction.DO_NOTHING

    # If the retention config is set, and does NOT equal what the template is, then we need to either Start or Stop the recorder:
    if not recording_enabled:
        return RecorderAction.STOP_RECORDING

    return RecorderAction.START_RECORDING


def determine_workload(current_state: Dict[str, Any], template: Dict[str, Any], account: str, region: str) -> Dict[str, Any]:
    """This is going to examine the current state and the template to determine if there is any work to do.

    This will take the template components, and make the dictionary that AWS would return. If it's not equal, then it adds it to a
    dictionary with that being the payload for calling AWS Config. It looks like this:
    {
        "ConfigurationRecorder": {...},
        "DeliveryChannel": {...},
        "EnableRecording": RecorderAction (enum),
        "RetentionConfig": {...}
    }
    """
    to_do = {}

    # Configuration recorder:
    to_do["ConfigurationRecorder"] = _make_configuration_recorder_payload(
        current_state["ConfigurationRecorder"], template["recorder_configuration"], account, region
    )

    # Delivery Channel:
    to_do["DeliveryChannel"] = _make_delivery_channel_payload(current_state["DeliveryChannel"], template["delivery_channel_details"])

    # Retention Config:
    to_do["RetentionConfig"] = _make_retention_config_payload(current_state["RetentionConfig"], template["retention_period_in_days"])

    # Recorder Status:
    to_do["EnableRecording"] = _make_recording_payload(current_state["RecorderStatus"], template["recorder_configuration"]["recording_enabled"])

    return to_do


def _log_summary(workload: Dict[str, Any]) -> bool:
    """
    This is a convenience function to log out the summary of what work needs to be done.

    This also returns a bool to indicate if there is work to do or not.
    """
    work_to_do = False

    # Print out the summary:
    if workload["ConfigurationRecorder"]:
        LOGGER.info(f"[🙅‍♂️] Configuration Recorder needs update with config: {workload['ConfigurationRecorder']}")
        work_to_do = True
    else:
        LOGGER.info("[🆗] Configuration Recorder is in sync.")

    if workload["DeliveryChannel"]:
        LOGGER.info(f"[🙅‍♂️] Delivery Channel needs update with config: {workload['DeliveryChannel']}")
        work_to_do = True
    else:
        LOGGER.info("[🆗] Delivery Channel is in sync.")

    if workload["RetentionConfig"]:
        LOGGER.info(f"[🙅‍♂️] Retention Configuration needs update with config: {workload['RetentionConfig']}")
        work_to_do = True
    else:
        LOGGER.info("[🆗] Retention Configuration is in sync.")

    if workload["EnableRecording"] == RecorderAction.START_RECORDING:
        LOGGER.info("[🙅‍♂️] The recorder needs to be enabled.")
        work_to_do = True
    elif workload["EnableRecording"] == RecorderAction.STOP_RECORDING:
        LOGGER.info("[🙅‍♂️] The recorder needs to be disabled.")
        work_to_do = True
    else:
        LOGGER.info("[🆗] The recorder's status is in sync.")

    return work_to_do


def sync_config(workload: Dict[str, Any], template: Dict[str, Any], account: str, region: str, assume_role: str, session_name: str, commit: bool) -> str:
    """This will sync the AWS Config details if the commit flag is set. This will also dump a summary of what the actions are."""
    LOGGER.info(f"[➕➖] Summarizing the items that are out of sync in {account}/{region}...")
    work_to_do = _log_summary(workload)
    alert_text = ""

    if not work_to_do:
        LOGGER.info(f"[✅] Nothing to do. Everything is all set in {account}/{region}.")
        return alert_text

    if not commit:
        LOGGER.info(f"[⏭️] There is work to do but because commit is disabled, no action is being taken in {account}/{region}.")
        return alert_text

    # Commit is enabled so fix it!
    # Configuration Recorder:
    if workload["ConfigurationRecorder"]:
        LOGGER.info("[📼] Fixing the Configuration Recorder...")
        put_configuration_recorder(
            ConfigurationRecorder=workload["ConfigurationRecorder"],
            account_number=account,
            region=region,
            assume_role=assume_role,
            session_name=session_name,
            sts_client_kwargs={"endpoint_url": f"https://sts.{region}.amazonaws.com", "region_name": region},
        )
        alert_text += "> ✅  Updated the Configuration Recorder\n"

    # Delivery Channel:
    if workload["DeliveryChannel"]:
        LOGGER.info("[🚚] Fixing the Delivery Channel...")
        put_delivery_channel(
            DeliveryChannel=workload["DeliveryChannel"],
            account_number=account,
            region=region,
            assume_role=assume_role,
            session_name=session_name,
            sts_client_kwargs={"endpoint_url": f"https://sts.{region}.amazonaws.com", "region_name": region},
        )
        alert_text += "> ✅  Updated the Delivery Channel\n"

    # Retention Configuration:
    if workload["RetentionConfig"]:
        LOGGER.info("[🗄️] Fixing the Retention Configuration...")
        put_retention_configuration(
            **workload["RetentionConfig"],
            account_number=account,
            region=region,
            assume_role=assume_role,
            session_name=session_name,
            sts_client_kwargs={"endpoint_url": f"https://sts.{region}.amazonaws.com", "region_name": region},
        )
        alert_text += "> ✅  Updated the Retention Configuration\n"

    # The recorder status:
    if workload["EnableRecording"] == RecorderAction.START_RECORDING:
        LOGGER.info("[⏺️] Staring the recorder...")
        start_configuration_recorder(
            ConfigurationRecorderName=template["recorder_configuration"]["preferred_name"],
            account_number=account,
            region=region,
            assume_role=assume_role,
            session_name=session_name,
            sts_client_kwargs={"endpoint_url": f"https://sts.{region}.amazonaws.com", "region_name": region},
        )
        alert_text += "> ✅  Started the Configuration Recorder\n"

    if workload["EnableRecording"] == RecorderAction.STOP_RECORDING:
        LOGGER.info("[🛑] Stopping the recorder...")
        stop_configuration_recorder(
            ConfigurationRecorderName=template["recorder_configuration"]["preferred_name"],
            account_number=account,
            region=region,
            assume_role=assume_role,
            session_name=session_name,
            sts_client_kwargs={"endpoint_url": f"https://sts.{region}.amazonaws.com", "region_name": region},
        )
        alert_text += "> ✅  Stopped the Configuration Recorder\n"

    LOGGER.info(f"[✅] Completed all work for {account}/{region}.")
    alert_text += "\n\nCheck out the Lambda logs for more verbose details."

    return alert_text
