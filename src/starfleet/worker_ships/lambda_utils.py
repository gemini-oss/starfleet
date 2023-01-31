"""Lambda utility functions for the worker ships.

This module contains a number of utility functions for worker ships, like decorators.

:Module: starfleet.worker_ships.lambda_utils
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
import os
from functools import wraps
from typing import Callable, Dict, Type, Any

from starfleet.utils.configuration import BadConfigurationError, STARFLEET_CONFIGURATION
from starfleet.utils.logging import LOGGER
from starfleet.worker_ships.ship_schematics import StarfleetWorkerShip


# Set up the configuration now so loggers are properly configured:
STARFLEET_CONFIGURATION.config  # noqa pylint: disable=W0104


def worker_lambda(worker_ship: Type[StarfleetWorkerShip]) -> Callable:
    """This is a decorator that does some convenience for the worker lambda handlers. You should always use this."""

    def wrapped_worker_lambda(func: Callable) -> Callable:
        """Because this decorator takes in an argument, you need to return the real decorator."""

        @wraps(func)
        def wrapped_lambda_handler(event: Dict[str, Any], context: object) -> None:  # noqa
            """This is the wrapped function that will inject the instantiated worker with the configuration all validated. This also handles the commit flag handling.

            This takes in all the standard lambda handler items.

            Example usage:

            YourWorkerShipInstance = TypeVar("YourWorkerShipInstance", bound=YourStarfleetWorkerShipClass)


            @worker_lambda(WorkerShipClass)
            def lambda_handler(event: Dict[str, Any], context: object, worker: YourWorkerShipInstance, commit: bool) -> None:
                for record in event["Records"]:
                    payload = json.loads(record["body"])

                    # Validate the payload: (don't worry about the exception handling -- that is done in the decorator!)
                    LOGGER.debug(f"[⚙️] Processing Payload: {payload}")
                    worker.load_template(payload)

                    # Process it!
                    worker.execute(commit=commit)
            """
            worker = worker_ship()
            LOGGER.info(f"[🛸] Starting the {worker.worker_ship_name} Worker Ship...")

            # Get the configuration:
            worker_config = STARFLEET_CONFIGURATION.config.get(worker.worker_ship_name, {})
            if not worker_config:
                LOGGER.error(f"[💥] Can't find configuration entry for: {worker.worker_ship_name}!")
                raise BadConfigurationError("[💥] No configuration found for the worker")

            errors = worker.configuration_template_class().validate(worker_config)
            if errors:
                LOGGER.error("[💥] Invalid configuration for the worker! See the stacktrace for details.")
                raise BadConfigurationError(f"[💥] Worker ship: {worker.worker_ship_name} has an invalid configuration. {str(errors)}")  # noqa

            # If any combination of the string "true" is present, then it's True. The default is thus False.
            commit = os.environ.get("STARFLEET_COMMIT", "").lower() == "true"

            try:
                func(event, context, worker, commit)
            except Exception:
                LOGGER.error("[💥] Encountered major problem processing the payload. See the stacktrace for details!")
                raise

        return wrapped_lambda_handler

    return wrapped_worker_lambda
