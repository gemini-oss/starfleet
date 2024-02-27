"""Starfleet's worker for dumping an account inventory to S3.

This is a worker ship that will periodically save an inventory of AWS accounts from the organizations API. This is the main implementation of it.
This contians the entrypoints for both the CLI and Lambda as well.

:Module: starfleet.worker_ships.plugins.account_index_generator.ship
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
from datetime import datetime
import json
from typing import Dict, Any, TypeVar

import boto3
import click
from click import Context
from marshmallow import fields

from starfleet.utils.configuration import STARFLEET_CONFIGURATION
from starfleet.utils.logging import LOGGER
from starfleet.worker_ships.cli_utils import StarfleetSingleInvokeCommand
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
            account_number=config["OrgAccountId"], assume_role=config["OrgAccountAssumeRole"], region="us-east-1"
        )
        account_map = get_account_map(all_accounts)  # Reformat the data

        # Fetch the list of org OUs for root:
        LOGGER.info("[📡] Reaching out to the Orgs API to get the list of all OUs under the ROOT OU...")
        all_ous = list_organizational_units_for_parent(  # pylint: disable=no-value-for-parameter
            ParentId=config["OrgRootId"], account_number=config["OrgAccountId"], assume_role=config["OrgAccountAssumeRole"], region="us-east-1"
        )

        # The resolved parents map: This is used to provide us with the parents for each account eventually pointing to ROOT.
        # At this point, we know that the top level OUs map to root, so we build that mapping list now so we don't have to resolve this later with lots of
        # unnecessary recursive API calls:
        root = {"Id": config["OrgRootId"], "Name": "ROOT", "Type": "ROOT"}
        resolved_parent_map = {ou["Id"]: [{"Id": ou["Id"], "Name": ou["Name"], "Type": "ORGANIZATIONAL_UNIT"}, root] for ou in all_ous}
        resolved_parent_map[config["OrgRootId"]] = [root]  # Any account that has a parent of ROOT will just have ROOT as the parent.

        # Fetch the tags and enabled regions:
        LOGGER.info("[🚚] Fetching tags and enabled regions for each account...")
        fetch_additional_details(
            account_map,
            resolved_parent_map,
            config["OrgAccountId"],
            config["OrgAccountAssumeRole"],
            config["DescribeRegionsAssumeRole"],
            STARFLEET_CONFIGURATION.config["STARFLEET"]["DeploymentRegion"],
        )

        # Save it to S3:
        if commit:
            dump_accounts = {"accounts": account_map, "generated": datetime.utcnow().replace(tzinfo=None, microsecond=0).isoformat() + "Z"}
            LOGGER.info(f"[🪣] Saving the report as {self.payload['inventory_object_prefix']} in {self.payload['account_inventory_bucket']}")
            client = boto3.client("s3", region_name=self.payload["inventory_bucket_region"])
            client.put_object(
                Bucket=self.payload["account_inventory_bucket"],
                Key=self.payload["inventory_object_prefix"],
                ACL="bucket-owner-full-control",
                Body=json.dumps(dump_accounts, indent=4, sort_keys=True),
                ContentType="application/json",
            )

        # If we are not committing, then just output the raw data out:
        else:
            LOGGER.info(f"[🍣] Raw Inventory:\n{json.dumps(account_map, sort_keys=True, indent=4)}")

        # Instructions for updating the testing account index:
        # If you need to update the index JSON for unit tests, uncomment the code below and run the tests for this plugin:
        # with open("generatedIndex.json", "w") as file:  # Uncomment this and the next line
        #     file.write(json.dumps({"accounts": account_map, "generated": datetime.utcnow().replace(tzinfo=None, microsecond=0).isoformat() + "Z"}, indent=4, sort_keys=True))
        # Then run the tests: `pytest tests/starfleet_included_plugins/account_index_generator`. That will generate a new index JSON.
        # Simply copy and paste this `generatedIndex.json` file to `tests/starfleet_included_plugins/account_index_generator/generatedIndex.json`
        # ‼️ Don't forget to re-comment the 2 lines above when done ‼️


@click.group()
@click.pass_context
def account_inventory(ctx: Context) -> None:
    """This is the worker ship for generating an S3 account inventory"""
    ctx.obj = AccountIndexGeneratorShip()


@account_inventory.command(cls=StarfleetSingleInvokeCommand, short_help="This will generate an AWS account inventory from the organizations API")
@click.pass_context
def generate(ctx: Context, commit: bool, **kwargs) -> None:  # noqa # pylint: disable=unused-argument
    """This will generate an AWS account inventory from the organizations API"""
    if not commit:
        LOGGER.warning("[⚠️] Commit flag is disabled: not saving report to S3")

    worker = ctx.obj
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
