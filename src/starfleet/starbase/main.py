"""Starfleet's main Starbase components

This defines all the major components and logic of the starbase

:Module: starfleet.starbase.main
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
from typing import Any, Dict

import boto3
from marshmallow import ValidationError

from starfleet.starbase.utils import account_fanout, account_region_fanout, fetch_template, list_worker_ship_templates, task_starbase_fanout
from starfleet.utils.configuration import STARFLEET_CONFIGURATION
from starfleet.utils.logging import LOGGER
from starfleet.worker_ships.base_payload_schemas import BaseAccountPayloadTemplate, BaseAccountRegionPayloadTemplate
from starfleet.worker_ships.loader import STARFLEET_WORKER_SHIPS
from starfleet.worker_ships.ship_schematics import EventBridgeFrequency, FanOutStrategy


class NoShipPluginError(Exception):
    """Raised if we receive a payload for a ship that doesn't exist."""


class InvalidTemplateForFanoutError(Exception):
    """Raised if the template Marshmallow class is invalid for the worker's fan out strategy."""


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
            if event_detail.name in config["EventBridgeTimedFrequency"]:
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


def fan_out_payload(payload: Dict[str, Any]) -> None:
    """This will fan out the workload for the given Starfleet worker."""
    ship_name = payload["worker_ship"]
    ship = STARFLEET_WORKER_SHIPS.get_worker_ships().get(ship_name)
    if not ship:
        LOGGER.error(
            f"[💥] Received payload for worker ship: {ship_name}, but that is not a recognized plugin. "
            f"Recognized plugins are: {list(STARFLEET_WORKER_SHIPS.get_worker_ships().keys())}."
        )
        raise NoShipPluginError(ship_name)

    template_prefix = payload["template_prefix"]
    starfleet_config = STARFLEET_CONFIGURATION.config["STARFLEET"]
    ship_config = STARFLEET_CONFIGURATION.config[ship_name]

    LOGGER.info(f"[🌟] Starbase tasking for ship: {ship_name} / template: {template_prefix}...")

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
        LOGGER.info(f"[🚀] Tasking worker ship: {ship_name}")
        # For the single fan out strategy, we just pass on the template (schema dumped from verified) without additional modification:
        sqs_client.send_message(QueueUrl=ship_config["InvocationQueueUrl"], MessageBody=schema.dumps(verified_template))
        LOGGER.info(f"[🛸] Worker Ship: {ship_name} tasked for the SINGLE_INVOCATION fan out")

    elif ship.fan_out_strategy == FanOutStrategy.ACCOUNT:
        if not isinstance(schema, BaseAccountPayloadTemplate):
            LOGGER.error(
                f"[❌] The worker ship: {ship_name} template class does not subclass the `BaseAccountPayloadTemplate`, which is required for `ACCOUNT` fan outs."
            )
            raise InvalidTemplateForFanoutError()

        LOGGER.info(f"[🚀] Tasking worker ship: {ship_name}")
        account_fanout(verified_template, schema, starfleet_config["TemplateBucket"], template_prefix, ship_config["InvocationQueueUrl"], sqs_client, ship_name)
        LOGGER.info(f"[🛸] Worker Ship: {ship_name} tasked for the ACCOUNT fan out")

    else:
        if not isinstance(schema, BaseAccountRegionPayloadTemplate):
            LOGGER.error(
                f"[❌] The worker ship: {ship_name} template class does not subclass the `BaseAccountRegionPayloadTemplate`, which is required for `ACCOUNT_REGION` fan outs."
            )
            raise InvalidTemplateForFanoutError()

        LOGGER.info(f"[🚀] Tasking worker ship: {ship_name}")
        account_region_fanout(
            verified_template, schema, starfleet_config["TemplateBucket"], template_prefix, ship_config["InvocationQueueUrl"], sqs_client, ship_name
        )
        LOGGER.info(f"[🛸] Worker Ship: {ship_name} tasked for the ACCOUNT_REGION fan out")
