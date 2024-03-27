"""Starfleet's main Starbase components

This defines all the major components and logic of the starbase

:Module: starfleet.starbase.main
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""

import json
from typing import Any, Dict, Tuple, Optional
from urllib.parse import unquote_plus

import boto3
from marshmallow import ValidationError

from starfleet.starbase.utils import account_fanout, account_region_fanout, fetch_template, list_worker_ship_templates, task_starbase_fanout
from starfleet.utils.configuration import STARFLEET_CONFIGURATION
from starfleet.utils.logging import LOGGER
from starfleet.worker_ships.base_payload_schemas import BaseAccountPayloadTemplate, BaseAccountRegionPayloadTemplate
from starfleet.worker_ships.loader import STARFLEET_WORKER_SHIPS
from starfleet.worker_ships.ship_schematics import EventBridgeFrequency, FanOutStrategy, StarfleetWorkerShipInstance


class NoShipPluginError(Exception):
    """Raised if we receive a payload for a ship that doesn't exist."""


class InvalidTemplateForFanoutError(Exception):
    """Raised if the template Marshmallow class is invalid for the worker's fan out strategy."""


class InvalidBucketError(Exception):
    """Raised if we receive an S3 notification for an S3 bucket that is NOT the Starfleet configured `TemplateBucket`"""


def process_eventbridge_timed_event(event: Dict[str, Any]) -> None:
    """This is the main logic for handling EventBridge timed events."""
    # Which timed event is this?
    event_detail = EventBridgeFrequency(event["name"])
    LOGGER.info(f"[⏰] Starbase received an EventBridge timed event: {event_detail.name}. Looking for worker ships to task.")
    starfleet_config = STARFLEET_CONFIGURATION.config["STARFLEET"]
    ships = STARFLEET_WORKER_SHIPS.get_worker_ships()

    # Which workers does this apply to?
    need_to_task = []
    for ship_name, worker_ship in ships.items():
        config = STARFLEET_CONFIGURATION.config[ship_name]

        # Does the worker ship listen to EventBridge?
        if "EVENTBRIDGE_TIMED_EVENT" in config["InvocationSources"]:
            # If yes, is this an event that it should care for?
            if event_detail.name == config["EventBridgeTimedFrequency"]:
                need_to_task.append((worker_ship, config))

    if not need_to_task:
        LOGGER.info(f"[🌑] No ships to task for the timed event: {event_detail.name}.")
        return

    LOGGER.debug(f"[🧑‍🚀] The following ships are being tasked: {[ship.worker_ship_name for ship, _ in need_to_task]}")

    # Now, we need to, for each worker ship, obtain a list of all S3 template objects to be scheduled for fan-out:
    sqs_client = boto3.client("sqs", region_name=starfleet_config["DeploymentRegion"])
    for worker, config in need_to_task:
        LOGGER.debug(f"[🗒️] Fetching list of templates for worker: {worker.worker_ship_name}...")
        worker_template_list = list_worker_ship_templates(
            starfleet_config["TemplateBucket"], starfleet_config["DeploymentRegion"], config["TemplatePrefix"], worker.worker_ship_name
        )

        if not worker_template_list:
            LOGGER.warning(f"[⚠️] No templates found for worker ship: {worker.worker_ship_name}. Skipping it.")
            continue

        # Task the Starbase for fan-out:
        LOGGER.info(f"[📡] Tasking fan-out for worker ship: {worker.worker_ship_name}...")
        task_starbase_fanout(worker_template_list, starfleet_config["FanOutQueueUrl"], sqs_client, worker.worker_ship_name)
        LOGGER.info(f"[🛰️] Completed tasking fan-out for worker ship: {worker.worker_ship_name}.")

    LOGGER.info(f"[🚀] All ships have been tasked for fan-out for this timed event: {event_detail.name}.")


def fan_out_payload(event_payload: Dict[str, Any]) -> None:
    """
    This will receive the fan out event and determine the type of event, fetch the worker ships plugins that are supposed to process the event, and fetch where in S3
    to obtain the template.
    """
    # Which type of event is this? Is a timed event for fan out, or is this an S3 event? TODO: Or something else?
    # Is there a top level key for `worker_ship`? If so then it's from the `process_eventbridge_timed_event` function:
    if event_payload.get("worker_ship"):
        _fan_out_payload_logic(*_fan_out_timed_events(event_payload))

    # Did we get an event from S3? - it's wrapped in another list of Records :/
    elif event_payload.get("Records"):
        if len(event_payload["Records"]) > 1:
            # TODO: S3 should not send multiple S3 events in one payload, however, the potential in the future to do
            # so does exist. If this happens, then we should add logic in place to re-task the fan out. For the time
            # being, we are just going to try to process each item.
            LOGGER.error(
                f"[🚨] Received {len(event_payload['Records'])} nested events! Going to loop over them, but "
                f"this should really be used to re-invoke the fan out!"
            )

        for record in event_payload["Records"]:
            if record.get("s3"):
                LOGGER.info("[🪣] Starbase received an S3 template modification event. Looking for the worker ship to task...")
                fanout_args = _fan_out_s3_events(record)

                if fanout_args:
                    _fan_out_payload_logic(*fanout_args)

            else:
                LOGGER.error(f"[👽] Received a nested record: `{record}` we don't support! Dropping it.")

    else:
        LOGGER.error(f"[👽] Received an event: `{event_payload}` we don't support! Dropping it.")


def _fan_out_timed_events(event_payload: Dict[str, Any]) -> Tuple[StarfleetWorkerShipInstance, str]:
    """
    Pulls out the details required to fan out EventBridge timed event payloads.

    This returns a Tuple of the StarfleetWorkerShip plugin object for this, and the template prefix.
    """
    ship_name = event_payload["worker_ship"]
    ship = STARFLEET_WORKER_SHIPS.get_worker_ships().get(ship_name)
    if not ship:
        LOGGER.error(
            f"[💥] Received payload for worker ship: {ship_name}, but that is not a recognized plugin. "
            f"Recognized plugins are: {list(STARFLEET_WORKER_SHIPS.get_worker_ships().keys())}."
        )
        raise NoShipPluginError(ship_name)

    template_prefix = event_payload["template_prefix"]

    return ship, template_prefix


def _fan_out_s3_events(event_payload: Dict[str, Any]) -> Optional[Tuple[StarfleetWorkerShipInstance, str]]:
    """
    Pulls out the details required to fan out S3 event payloads.

    This returns a Tuple of the StarfleetWorkerShip plugin object for this, and the template prefix -- ONLY
    if we locate the worker and if the worker is configured to execute on S3 events in the configuration. If not, then this returns `None`.
    """
    bucket = event_payload["s3"]["bucket"]["name"]
    # Is the bucket name different from what we have configured in Starfleet?
    if STARFLEET_CONFIGURATION.config["STARFLEET"]["TemplateBucket"] != bucket:
        LOGGER.error(
            f"[❌] We received an S3 event notification that is supposed to work with S3 bucket: {bucket}, "
            f"but we are only configured for S3 events for bucket: {STARFLEET_CONFIGURATION.config['STARFLEET']['TemplateBucket']}"
        )
        raise InvalidBucketError()

    template_prefix = unquote_plus(event_payload["s3"]["object"]["key"])  # It's URL encoded, so we need to decode it.
    LOGGER.info(f"[🧾] S3 object that was modified was: {template_prefix}.")
    # The template prefix must end in `.yaml` or we don't process it:
    if not template_prefix.endswith(".yaml"):
        LOGGER.warning(
            f"[⏭️] Received an object prefix that is not a recognized template: {template_prefix}. We only process files that end in `.yaml`. Skipping."
        )
        return None

    # Now we need to identify the worker that cares about this template (if we can find it!):
    ships = STARFLEET_WORKER_SHIPS.get_worker_ships()
    found_ship = None
    for ship_name, worker_ship in ships.items():
        config = STARFLEET_CONFIGURATION.config[ship_name]

        # Does the worker ship listen to S3 events?
        if "S3" in config["InvocationSources"]:
            # If yes, is this worker configured for the prefix in question?
            # First, check if the worker ship cares about all files within a path:
            if config["TemplatePrefix"].endswith(".yaml") and config["TemplatePrefix"] == template_prefix:
                found_ship = worker_ship
                break

            # Ends in `/` or a path, we need to make sure that the prefix of this template is in fact supposed to apply to this worker ship:
            if template_prefix.startswith(config["TemplatePrefix"]):
                found_ship = worker_ship
                break

    # Did we find our ship?
    if not found_ship:
        LOGGER.warning(f"[⏭️] Received S3 payload for object: {template_prefix} that we can't find a ship to handle. Skipping.")
        return None

    LOGGER.info(f"[🧑‍🚀] Identified worker ship: {found_ship.worker_ship_name} for S3 template: {template_prefix}.")
    return found_ship, template_prefix


def _fan_out_payload_logic(ship: StarfleetWorkerShipInstance, template_prefix: str) -> None:
    """This will fan out the workload for the given Starfleet worker."""
    starfleet_config = STARFLEET_CONFIGURATION.config["STARFLEET"]
    ship_config = STARFLEET_CONFIGURATION.config[ship.worker_ship_name]

    LOGGER.info(f"[🌟] Starbase tasking for ship: {ship.worker_ship_name} / template: {template_prefix}...")

    # Get the template from S3:
    LOGGER.debug(f"[🪣] Fetching the template: {template_prefix} from bucket: {starfleet_config['TemplateBucket']}...")
    client = boto3.client("s3", region_name=starfleet_config["DeploymentRegion"])
    template = fetch_template(client, starfleet_config["TemplateBucket"], template_prefix)

    # Validate the template per the worker's payload schema:
    try:
        schema = ship.payload_template_class()
        verified_template = schema.load(template)
    except ValidationError as exc:
        LOGGER.error(f"[❌] Errors in the payload template: {str(exc)}. See stacktrace for details.")
        raise

    # Now is the important part: Tasking the worker ships based on the type of fan out strategy:
    sqs_client = boto3.client("sqs", region_name=starfleet_config["DeploymentRegion"])
    if ship.fan_out_strategy == FanOutStrategy.SINGLE_INVOCATION:
        LOGGER.info(f"[🚀] Tasking worker ship: {ship.worker_ship_name}")
        # For the single fan out strategy, we just pass on the template without additional modification:
        sqs_client.send_message(QueueUrl=ship_config["InvocationQueueUrl"], MessageBody=json.dumps(template))
        LOGGER.info(f"[🛸] Worker Ship: {ship.worker_ship_name} tasked for the SINGLE_INVOCATION fan out")

    elif ship.fan_out_strategy == FanOutStrategy.ACCOUNT:
        if not isinstance(schema, BaseAccountPayloadTemplate):
            LOGGER.error(
                f"[❌] The worker ship: {ship.worker_ship_name} template class does not subclass the `BaseAccountPayloadTemplate`, which is required for `ACCOUNT` fan outs."
            )
            raise InvalidTemplateForFanoutError()

        LOGGER.info(f"[🚀] Tasking worker ship: {ship.worker_ship_name}")
        account_fanout(
            verified_template,
            template,
            starfleet_config["TemplateBucket"],
            template_prefix,
            ship_config["InvocationQueueUrl"],
            sqs_client,
            ship.worker_ship_name,
        )
        LOGGER.info(f"[🛸] Worker Ship: {ship.worker_ship_name} tasked for the ACCOUNT fan out")

    else:
        if not isinstance(schema, BaseAccountRegionPayloadTemplate):
            LOGGER.error(
                f"[❌] The worker ship: {ship.worker_ship_name} template class does not subclass the `BaseAccountRegionPayloadTemplate`, "
                "which is required for `ACCOUNT_REGION` fan outs."
            )
            raise InvalidTemplateForFanoutError()

        LOGGER.info(f"[🚀] Tasking worker ship: {ship.worker_ship_name}")
        account_region_fanout(
            verified_template,
            template,
            starfleet_config["TemplateBucket"],
            template_prefix,
            ship_config["InvocationQueueUrl"],
            sqs_client,
            ship.worker_ship_name,
        )
        LOGGER.info(f"[🛸] Worker Ship: {ship.worker_ship_name} tasked for the ACCOUNT_REGION fan out")
