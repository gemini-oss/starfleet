"""AWS Config enablement worker ship

This is a worker ship that will operate over all accounts/regions to enable a consistent AWS Config recording configuration. This will also allow you
to easily specify per-account/region configuration details for each recorder.

:Module: starfleet.worker_ships.plugins.aws_config.ship
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
import json
import traceback
from typing import Dict, Any, TypeVar

import click
from click import Context

from starfleet.utils.configuration import STARFLEET_CONFIGURATION
from starfleet.utils.logging import LOGGER
from starfleet.worker_ships.cli_utils import StarfleetAccountRegionCommand
from starfleet.worker_ships.lambda_utils import worker_lambda

from starfleet.worker_ships.plugins.aws_config.logic import get_account_region_payload, get_current_state, determine_workload, sync_config
from starfleet.worker_ships.plugins.aws_config.schemas import AwsConfigWorkerShipConfigurationTemplate, AwsConfigWorkerShipPayloadTemplate
from starfleet.worker_ships.ship_schematics import FanOutStrategy, StarfleetWorkerShip, AlertPriority


class AwsConfigWorkerShip(StarfleetWorkerShip):
    """This is a worker that will enable AWS Config recording in each account/region specified."""

    worker_ship_name = "AwsConfigWorkerShip"
    configuration_template_class = AwsConfigWorkerShipConfigurationTemplate
    payload_template_class = AwsConfigWorkerShipPayloadTemplate
    fan_out_strategy = FanOutStrategy.ACCOUNT_REGION

    def execute(self, commit: bool = False) -> None:
        """Execute the payload to enable AWS Config."""
        config = self.configuration_template_class().load(STARFLEET_CONFIGURATION.config[self.worker_ship_name])

        # Pull out the payload details for this account/region pair:
        account = self.payload["starbase_assigned_account"]
        region = self.payload["starbase_assigned_region"]
        working_payload = get_account_region_payload(self.payload, account, region)

        # Get the current state of AWS Config in this account/region:
        LOGGER.info(f"[🧺] Fetching the current AWS Config state in {account}/{region}...")
        assume_role = config["worker_role_to_assume"]
        session_name = config["worker_role_session_name"]
        current_state = get_current_state(account, region, assume_role, session_name)
        workload = determine_workload(current_state, working_payload, account, region)

        # Do the work!
        alert_text = sync_config(workload, working_payload, account, region, assume_role, session_name, commit)
        if commit and alert_text:
            self.send_alert(
                AlertPriority.SUCCESS, "Updated AWS Config properties", f"*Below is a summary of the work performed in {account}/{region}:*\n\n" + alert_text
            )


@click.group()
@click.pass_context
def aws_config(ctx: Context) -> None:
    """This is the worker ship for enabling AWS Config."""
    ctx.obj = AwsConfigWorkerShip()


@aws_config.command(cls=StarfleetAccountRegionCommand)
@click.pass_context
def sync(ctx: Context, commit: bool, **kwargs) -> None:  # noqa # pylint: disable=unused-argument
    """This will sync the AWS Config payload in the desired account and region."""
    if not commit:
        LOGGER.warning("[⚠️] Commit flag is disabled: not making any changes")

    worker = ctx.obj
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
        try:
            worker.execute(commit=commit)
        except Exception:
            message_text = (
                f"*Error processing AWS Config template: {worker.payload['template_name']}*\n"
                + f"*Unable to update the AWS Config configuration in: {worker.payload['starbase_assigned_account']}/{worker.payload['starbase_assigned_region']}.*\n\n"
                + f"The exception details are below:\n```\n{traceback.format_exc()}```"
            )
            worker.send_alert(AlertPriority.PROBLEM, f"Problem updating AWS Config properties for template: {worker.payload['template_name']}", message_text)
            raise

    LOGGER.info("[🏁] Completed syncing the AWS Config template.")
