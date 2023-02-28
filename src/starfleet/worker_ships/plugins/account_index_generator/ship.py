"""Starfleet's worker for dumping an account inventory to S3.

This is a worker ship that will periodically save an inventory of AWS accounts from the organizations API. This is the main implementation of it.
This contians the entrypoints for both the CLI and Lambda as well.

:Module: starfleet.worker_ships.plugins.account_index_generator.ship
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
import json
from typing import Dict, Any, TypeVar

import boto3
import click
from marshmallow import fields

from starfleet.utils.configuration import STARFLEET_CONFIGURATION
from starfleet.utils.logging import LOGGER
from starfleet.worker_ships.cli_utils import load_payload
from starfleet.worker_ships.lambda_utils import worker_lambda
from starfleet.worker_ships.plugins.account_index_generator.utils import (
    fetch_additional_details,
    list_accounts,
    get_account_map,
    list_organizational_units_for_parent,
)
from starfleet.worker_ships.ship_schematics import StarfleetWorkerShip, WorkerShipBaseConfigurationTemplate
from starfleet.worker_ships.base_payload_schemas import WorkerShipPayloadBaseTemplate


class AccountIndexGeneratorShipConfigurationTemplate(WorkerShipBaseConfigurationTemplate):
    """The configuration for the AccountIndexGeneratorShip. This largely defines where the Organization root is and the role to assume to query for accounts."""

    org_account_assume_role = fields.String(required=True, data_key="OrgAccountAssumeRole")
    org_account_id = fields.String(required=True, data_key="OrgAccountId")
    org_root_id = fields.String(required=True, data_key="OrgRootId")  # Needed to list all the OUs. Get from the AWS Orgs console. Starts with `r-...`
    describe_regions_assume_role = fields.String(required=True, data_key="DescribeRegionsAssumeRole")


class AccountIndexGeneratorShipPayloadTemplate(WorkerShipPayloadBaseTemplate):
    """The payload for the AccountIndexGeneratorShip. This largely defines the S3 buckets to dump the report to."""

    account_inventory_bucket = fields.String(required=True, data_key="AccountInventoryBucket")
    inventory_bucket_region = fields.String(required=True, data_key="InventoryBucketRegion")
    inventory_object_prefix = fields.String(required=False, data_key="InventoryObjectPrefix", load_default="accountIndex.json")


class AccountIndexGeneratorShip(StarfleetWorkerShip):
    """This is a worker that will periodically dump out a summary of the AWS Organizations accounts to S3."""

    worker_ship_name = "AccountIndexGeneratorShip"
    configuration_template_class = AccountIndexGeneratorShipConfigurationTemplate
    payload_template_class = AccountIndexGeneratorShipPayloadTemplate

    def execute(self, commit: bool = False) -> None:
        """Execute the payload to dump the workload to S3."""
        config = STARFLEET_CONFIGURATION.config[self.worker_ship_name]
        LOGGER.info(f"[📡] Reaching out to the Orgs API to get the list of AWS accounts in account: {config['OrgAccountId']}...")
        all_accounts = list_accounts(  # pylint: disable=no-value-for-parameter
            account_number=config["OrgAccountId"], assume_role=config["OrgAccountAssumeRole"]
        )
        account_map = get_account_map(all_accounts)  # Reformat the data

        # Fetch the list of org OUs:
        LOGGER.info("[📡] Reaching out to the Orgs API to get the list of all OUs in the org...")
        all_ous = list_organizational_units_for_parent(  # pylint: disable=no-value-for-parameter
            ParentId=config["OrgRootId"], account_number=config["OrgAccountId"], assume_role=config["OrgAccountAssumeRole"]
        )
        ou_map = {ou["Id"]: ou["Name"] for ou in all_ous}  # noqa  # Reformat the data into a nice map
        ou_map[config["OrgRootId"]] = "ROOT"  # Add the root in

        # Fetch the tags and enabled regions:
        LOGGER.info("[🚚] Fetching tags and enabled regions for each account...")
        fetch_additional_details(
            account_map,
            ou_map,
            config["OrgRootId"],
            config["OrgAccountId"],
            config["OrgAccountAssumeRole"],
            config["DescribeRegionsAssumeRole"],
            STARFLEET_CONFIGURATION.config["STARFLEET"]["DeploymentRegion"],
        )

        # Save it to S3:
        if commit:
            LOGGER.info(f"[🪣] Saving the report as {self.payload['inventory_object_prefix']} in {self.payload['account_inventory_bucket']}")
            client = boto3.client("s3", region_name=self.payload["inventory_bucket_region"])
            client.put_object(
                Bucket=self.payload["account_inventory_bucket"],
                Key=self.payload["inventory_object_prefix"],
                ACL="bucket-owner-full-control",
                Body=json.dumps(account_map, indent=4),
                ContentType="application/json",
            )

        # If we are not committing, then just output the raw data out:
        else:
            LOGGER.info(f"[🍣] Raw Inventory:\n{json.dumps(account_map, indent=4)}")


@click.group()
def account_inventory() -> None:
    """This is the worker ship for generating an S3 account inventory"""


@account_inventory.command()
@click.option("--payload", required=True, type=click.File("r"), callback=load_payload, help="This is the worker payload YAML")
@click.option("--commit", is_flag=True, default=False, show_default=True, help="Must be supplied for changes to be made")
def generate(payload: Dict[str, Any], commit: bool) -> None:
    """This will generate an AWS account inventory from the organizations API"""
    if not commit:
        LOGGER.warning("[⚠️] Commit flag is disabled: not saving report to S3")

    worker = AccountIndexGeneratorShip()
    worker.load_template(payload)
    worker.execute(commit=commit)

    LOGGER.info("[✅] Done!")


AccountIndexGeneratorShipInstance = TypeVar("AccountIndexGeneratorShipInstance", bound=AccountIndexGeneratorShip)


@worker_lambda(AccountIndexGeneratorShip)
def lambda_handler(event: Dict[str, Any], context: object, worker: AccountIndexGeneratorShipInstance, commit: bool) -> None:  # noqa pylint: disable=W0613
    """This is the Lambda entrypoint for the AccountIndexGeneratorShip event from the Starbase."""
    for record in event["Records"]:
        # Load the payload:
        payload = json.loads(record["body"])
        LOGGER.debug(f"[⚙️] Processing Payload: {payload}")
        worker.load_template(payload)

        # Process it!
        worker.execute(commit=commit)

    LOGGER.info("[🏁] Completed generating the account index.")
