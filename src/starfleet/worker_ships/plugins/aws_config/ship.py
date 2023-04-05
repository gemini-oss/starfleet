"""AWS Config enablement worker ship

This is a worker ship that will operate over all accounts/regions to enable a consistent AWS Config recording configuration. This will also allow you
to easily specify per-account/region configuration details for each recorder.

:Module: starfleet.worker_ships.plugins.aws_config.ship
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
import json
from typing import Dict, Any, TypeVar

import click

# from starfleet.utils.configuration import STARFLEET_CONFIGURATION
from starfleet.utils.logging import LOGGER
from starfleet.worker_ships.cli_utils import load_payload
from starfleet.worker_ships.lambda_utils import worker_lambda
from starfleet.worker_ships.plugins.aws_config.schemas import AwsConfigWorkerShipConfigurationTemplate, AwsConfigWorkerShipPayloadTemplate
from starfleet.worker_ships.ship_schematics import FanOutStrategy, StarfleetWorkerShip


class AwsConfigWorkerShip(StarfleetWorkerShip):
    """This is a worker that will enable AWS Config recording in each account/region specified."""

    worker_ship_name = "AwsConfigWorkerShip"
    configuration_template_class = AwsConfigWorkerShipConfigurationTemplate
    payload_template_class = AwsConfigWorkerShipPayloadTemplate
    fan_out_strategy = FanOutStrategy.ACCOUNT_REGION

    def execute(self, commit: bool = False) -> None:
        """Execute the payload to enable AWS Config."""
        raise NotImplementedError("Soon!")
        # config = STARFLEET_CONFIGURATION.config[self.worker_ship_name]
        #
        # # Sync it!
        # if commit:
        #     pass
        #
        # else:
        #     pass


@click.group()
def aws_config() -> None:
    """This is the worker ship for enabling AWS Config."""


@aws_config.command()
@click.option("--payload", required=True, type=click.File("r"), callback=load_payload, help="This is the worker payload YAML")
@click.option("--account-id", required=True, type=str, help="The AWS account ID to operate in")
@click.option("--region", required=True, type=str, help="The AWS region to operate in")
@click.option("--commit", is_flag=True, default=False, show_default=True, help="Must be supplied for changes to be made")
def sync(payload: Dict[str, Any], account_id: str, region: str, commit: bool) -> None:
    """This will sync the AWS Config payload in the desired account and region."""
    if not commit:
        LOGGER.warning("[⚠️] Commit flag is disabled: not making any changes")

    # TODO Remove this once implemented:
    LOGGER.debug(f"{account_id}/{region}")

    worker = AwsConfigWorkerShip()
    worker.load_template(payload)
    worker.execute(commit=commit)

    LOGGER.info("[✅] Done!")


AwsConfigWorkerShipInstance = TypeVar("AwsConfigWorkerShipInstance", bound=AwsConfigWorkerShip)


@worker_lambda(AwsConfigWorkerShip)
def lambda_handler(event: Dict[str, Any], context: object, worker: AwsConfigWorkerShipInstance, commit: bool) -> None:  # noqa pylint: disable=W0613
    """This is the Lambda entrypoint for the AwsConfigWorkerShip event from the Starbase."""
    for record in event["Records"]:
        # Load the payload:
        payload = json.loads(record["body"])
        LOGGER.debug(f"[⚙️] Processing Payload: {payload}")
        worker.load_template(payload)

        # Process it!
        worker.execute(commit=commit)

    LOGGER.info("[🏁] Completed syncing the AWS Config template.")
