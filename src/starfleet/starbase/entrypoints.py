"""Starbase Lambda Entrypoints

All of the Lambda entrypoints for the Starbase are here.

:Module: starfleet.starbase.entrypoints
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""

import json
from typing import Any, Dict

from starfleet.startup import starbase_start_up
from starfleet.starbase.main import fan_out_payload, process_eventbridge_timed_event
from starfleet.utils.logging import LOGGER


def eventbridge_timed_lambda_handler(event: Dict[str, Any], context: object) -> None:  # noqa pylint: disable=W0613
    """This is the Lambda entrypoint for the EventBridge timed events."""
    starbase_start_up()

    LOGGER.info("[🎬] Starting Starbase for EventBridge timed event...")
    process_eventbridge_timed_event(event)
    LOGGER.info("[🏁] Completed Starbase EventBridge timed event.")


def fanout_payload_lambda_handler(event: Dict[str, Any], context: object) -> None:  # noqa pylint: disable=W0613
    """This is the Lambda entrypoint that will fan out the workload to all worker ships for the given template."""
    starbase_start_up()

    LOGGER.info("[🎬] Starting Starbase Worker Ship fanout...")

    # This should not!! be a list, but if it is, just handle it anyway:
    if len(event["Records"]) > 1:
        LOGGER.error("[🚨] Received more than 1 event for fan out! This should only receive 1, but handling it anyway...")

    for record in event["Records"]:
        payload = json.loads(record["body"])
        fan_out_payload(payload)

    LOGGER.info("[🏁] Completed Starbase Worker Ship fanout.")
