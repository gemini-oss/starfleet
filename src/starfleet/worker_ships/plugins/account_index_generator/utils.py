"""Starfleet's worker for saving an account inventory JSON to S3: the utility functions

This is a worker ship that will periodically save an inventory of AWS accounts from the organizations API. These are the utility functions that the worker ship uses.

:Module: starfleet.worker_ships.plugins.account_index_generator.utils
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
import asyncio
from asyncio import AbstractEventLoop
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple
import re

import boto3
from retry import retry
from botocore.client import BaseClient
from cloudaux import sts_conn
from cloudaux.aws.sts import boto3_cached_conn
from cloudaux.aws.decorators import paginated

from starfleet.utils.logging import LOGGER


# Represents a valid AWS Organizations root ID, accepting either the standalone ID,
# or the fully-qualified ARN. For example:
#   >>> arn:aws:organizations::123456789012:root/o-ca45vq09vj/r-aux4
#   >>> r-aux4
ORGANIZATION_ROOT_ID_PATTERN: re.Pattern = re.compile(r"(^arn:aws:organizations::\d{12}:root/o-[a-z0-9]{10,32}/r-[0-9a-z]{4,32}$)|(^r-[0-9a-z]{4,32}$)")


class AccountIndexerProcessError(Exception):
    """Exception raised if there were issues pulling additional account details from the process pool."""


@sts_conn("organizations")
@paginated("Accounts", request_pagination_marker="NextToken", response_pagination_marker="NextToken")
def list_accounts(client: BaseClient, **kwargs) -> Dict[str, Any]:
    """This will query organizations to list all accounts -- calls are wrapped by CloudAux"""
    return client.list_accounts(**kwargs)


@sts_conn("organizations")
@paginated("OrganizationalUnits", request_pagination_marker="NextToken", response_pagination_marker="NextToken")
def list_organizational_units_for_parent(client: BaseClient, **kwargs) -> Dict[str, Any]:
    """This will list all the OUs for the given parent -- calls are wrapped by CloudAux"""
    return client.list_organizational_units_for_parent(**kwargs)  # pragma: no cover


def get_organizational_unit_map(
    parent_id: str,
    org_account_id: str,
    org_account_role_name: str,
    client: Optional[BaseClient] = None,
) -> dict[str, Any]:
    """Recursively lists all OUs contained Returns a map of all OU names keyed to their identifier, searching recursively."""
    ou_map: dict[str, str] = {}
    if client is None:
        client: BaseClient = boto3_cached_conn(service="organizations", account_number=org_account_id, assume_role=org_account_role_name)
    if ORGANIZATION_ROOT_ID_PATTERN.fullmatch(parent_id):
        ou_map[parent_id] = "ROOT"
    paginator = client.get_paginator("list_organizational_units_for_parent")
    response = paginator.paginate(ParentId=parent_id).build_full_result()
    for organizational_unit in response["OrganizationalUnits"]:
        ou_map.update({organizational_unit["Id"]: organizational_unit["Name"]})
        ou_map.update(
            get_organizational_unit_map(
                parent_id=organizational_unit["Id"], org_account_id=org_account_id, org_account_role_name=org_account_role_name, client=client
            )
        )
    return ou_map


@paginated("Tags", request_pagination_marker="NextToken", response_pagination_marker="NextToken")
def list_tags_for_resource(client: BaseClient, **kwargs) -> Dict[str, Any]:
    """This will query organizations to list all tags for a given account -- calls are wrapped by CloudAux"""
    return client.list_tags_for_resource(**kwargs)


@paginated("Parents", request_pagination_marker="NextToken", response_pagination_marker="NextToken")
def list_parents(client: BaseClient, **kwargs) -> Dict[str, Any]:
    """This will query organizations to list all the parent OUs and Root for a given account -- calls are wrapped by CloudAux"""
    return client.list_parents(**kwargs)


def get_account_map(account_list: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Returns a map of Account ID -> Account Blob."""
    account_map = {}
    for account in account_list:
        # Convert the datetimes into strings:
        account["JoinedTimestamp"] = str(account["JoinedTimestamp"])

        # Add it to our ID -> Account Map:
        account_map[account["Id"]] = account

    return account_map


@retry(tries=3, jitter=(0, 3), delay=1, backoff=2, max_delay=3, logger=LOGGER)
def fetch_tags_and_parents(account_id: str, creds: Dict[str, str], deployment_region: str) -> Tuple[str, Dict[str, str], List[Dict[str, str]]]:
    """Fetch the tags and parent OUs for each individual account"""
    LOGGER.debug(f"[🏷️] Fetching tags for account id: {account_id}...")
    client = boto3.client(
        "organizations",
        region_name=deployment_region,
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
    )
    returned_tags = list_tags_for_resource(client, ResourceId=account_id)
    extracted_tags = {tag["Key"]: tag["Value"] for tag in returned_tags}

    LOGGER.debug(f"[👪] Fetching parents for account id: {account_id}...")
    returned_parents = list_parents(client, ChildId=account_id)

    return account_id, extracted_tags, returned_parents


@retry(tries=3, jitter=(0, 3), delay=1, backoff=2, max_delay=3, logger=LOGGER)
def fetch_regions(account_id: str, assume_role: str, deployment_region: str) -> Tuple[str, List[str]]:
    """Fetch the list of enabled regions in the given account."""
    # First, we need to assume the role to the target account:
    LOGGER.debug(f"[🌍️] Fetching enabled regions for account id: {account_id}...")
    sts_client = boto3.client("sts", region_name=deployment_region)
    creds = sts_client.assume_role(RoleArn=f"arn:aws:iam::{account_id}:role/{assume_role}", RoleSessionName="StarfleetAccountIndexer")["Credentials"]

    # Now query EC2 for the regions:
    ec2_client = boto3.client(
        "ec2",
        region_name=deployment_region,
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
    )

    response = ec2_client.describe_regions()["Regions"]
    enabled_regions = sorted([item["RegionName"] for item in response])

    return account_id, enabled_regions


TagAndParentResults = List[Tuple[str, Dict[str, str], List[Dict[str, str]]]]
RegionsResults = List[Tuple[str, List[str]]]


# pylint: disable=too-many-locals
async def fetch_additional_async(
    loop: AbstractEventLoop, all_accounts: Dict[str, Any], org_id: str, org_role: str, region_role: str, deployment_region: str
) -> Tuple[TagAndParentResults, RegionsResults]:
    """This is an async that will task on the event loop the task to pull out both the tags for each account and also the enabled regions"""
    # Unfortunately ProcessPoolExecutors are not supported on Lambda 😭, so we need to use the inferior ThreadPoolExecutor instead 😒
    with ThreadPoolExecutor(max_workers=20) as executor:
        # Create the STS client for tag collection:
        sts_client = boto3.client("sts", region_name=deployment_region)
        creds = sts_client.assume_role(RoleArn=f"arn:aws:iam::{org_id}:role/{org_role}", RoleSessionName="StarfleetAccountIndexer")["Credentials"]
        creds.pop("Expiration")

        # Task the tag and region fetching:
        tag_and_parent_tasks = []
        regions_tasks = []

        for account_id in all_accounts.keys():
            tag_and_parent_tasks.append(loop.run_in_executor(executor, fetch_tags_and_parents, account_id, creds, deployment_region))
            regions_tasks.append(loop.run_in_executor(executor, fetch_regions, account_id, region_role, deployment_region))

        try:
            tag_and_parent_results = await asyncio.gather(*tag_and_parent_tasks)
            region_results = await asyncio.gather(*regions_tasks)
        except Exception as err:
            LOGGER.error(f"[💥] Encountered an error fetching tags and regions. Details: {str(err)}")
            LOGGER.exception(err)
            raise AccountIndexerProcessError("Fetching tags and regions", err) from err

    return tag_and_parent_results, region_results  # noqa


def fetch_additional_details(
    all_accounts: Dict[str, Any], all_ous: Dict[str, str], root_id: str, org_id: str, org_role: str, region_role: str, deployment_region: str
) -> None:
    """This is the function that will go out and fetch all the additional details asynchronously with multiple spun processes. This wraps everything
    in the event loop."""
    loop = asyncio.new_event_loop()
    try:
        tag_and_parent_results, region_results = loop.run_until_complete(
            fetch_additional_async(loop, all_accounts, org_id, org_role, region_role, deployment_region)
        )
    finally:
        loop.close()

    # Merge in the tag and parent details:
    for result in tag_and_parent_results:
        all_accounts[result[0]]["Tags"] = result[1]

        parent_ous = []
        has_root = False  # If the Root wasn't added in, then we will append it so that there is a full chain up to the Root.
        for parent in result[2]:
            if parent["Type"] == "ROOT":
                has_root = True

            parent_ous.append({"Id": parent["Id"], "Type": parent["Type"], "Name": all_ous[parent["Id"]]})

        # If Root wasn't there, then append it:
        if not has_root:
            parent_ous.append({"Id": root_id, "Type": "ROOT", "Name": "ROOT"})

        all_accounts[result[0]]["Parents"] = parent_ous

    for result in region_results:
        all_accounts[result[0]]["Regions"] = result[1]

    # Nothing to return because the Dictionary contents are updated by reference.
