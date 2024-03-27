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
from typing import Any, Dict, List, Tuple

import boto3
from retry import retry
from botocore.client import BaseClient
from cloudaux import sts_conn
from cloudaux.aws.decorators import paginated

from starfleet.utils.logging import LOGGER


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
    return client.list_organizational_units_for_parent(**kwargs)


@sts_conn("organizations")
def describe_organizational_unit(client: BaseClient, **kwargs) -> Dict[str, Any]:
    """This will describe the OU given the OU ID. This is used to extract the name of the OU -- calls are wrapped by CloudAux"""
    return client.describe_organizational_unit(**kwargs)


@paginated("Tags", request_pagination_marker="NextToken", response_pagination_marker="NextToken")
def list_tags_for_resource(client: BaseClient, **kwargs) -> Dict[str, Any]:
    """This will query organizations to list all tags for a given account -- calls are wrapped by CloudAux"""
    return client.list_tags_for_resource(**kwargs)


@sts_conn("organizations")
@paginated("Parents", request_pagination_marker="NextToken", response_pagination_marker="NextToken")
def list_parents(client: BaseClient, **kwargs) -> Dict[str, Any]:
    """This will query organizations to list the immediate parent a given account or OU -- calls are wrapped by CloudAux"""
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
def fetch_tags_and_parent(account_id: str, creds: Dict[str, str], deployment_region: str) -> Tuple[str, Dict[str, str], List[Dict[str, str]]]:
    """Fetch the tags and the immediate parent OU for each individual account"""
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
    returned_parent = list_parents(force_client=client, ChildId=account_id)  # pylint: disable=no-value-for-parameter

    return account_id, extracted_tags, returned_parent


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


@retry(tries=3, jitter=(0, 3), delay=1, backoff=2, max_delay=3, logger=LOGGER)
def resolve_parents(ou_dict: Dict[str, Any], resolved_parents: Dict[str, List[Dict[str, str]]], org_account_id: str, assume_role: str) -> List[Dict[str, Any]]:
    """
    This will resolve the parents for a given account's parent OU. the `resolved_parents` map is a dictionary that contains a list of the parents for the given OU ID passed in.
    If we have an OU ID that is not resolved, then we need to build the parent tree for it. This involves recursively calling the list_parents call so that we can
    resolve all parents up to one that we have already resolved parents for.

    Before this function runs, the `resolved_parents` parameter should at a minimum have the ROOT resolved. It should also have all the ROOT's immediate children OUs resolved
    as well.

    This function is required to address issue #24. Orgs does not provide an API to just get the Org OU tree. When this worker ship first runs, we list the OUs that are under
    the ROOT, but that doesn't list all the nested OUs. This addresses that by fetching and updating the map as missing OUs are encountered. Very annoying but is required. :/
    """
    ou_id = ou_dict["Id"]
    if parents := resolved_parents.get(ou_id):
        return parents

    # We have not yet resolved the parent OUs and we need to resolve it:
    LOGGER.debug(f"[🌲] Need to query the Orgs API to fetch the parents for OU ID: {ou_dict['Id']}...")

    # We also need to get the name of this OU because we haven't seen it yet:
    ou_response = describe_organizational_unit(  # pylint: disable=no-value-for-parameter
        OrganizationalUnitId=ou_dict["Id"], account_number=org_account_id, assume_role=assume_role, region="us-east-1"
    )["OrganizationalUnit"]
    resolved_ou = {"Name": ou_response["Name"], "Id": ou_id, "Type": "ORGANIZATIONAL_UNIT"}
    LOGGER.debug(f"[🆔] OU ID: {ou_id} has name: {ou_response['Name']}.")

    # Append this OU as the first parent in the list:
    resolved_parents[ou_id] = [resolved_ou]

    # Unfortunately, when we list_parents, we only get back the immediate parent. This sucks. So we need to have the following logic:
    # 1. Get the immediate parent that is returned (it should only be 1) -- but it's a list that's returned.
    # 2. Call this function again (recurse) with the parent provided. Keep going until we find a parent we know about (we should always map to ROOT at a minimum).
    # 3. As we continue, we are traversing the Org tree. As we go along we continue to update the parents and grandparents parents
    # 4. After the tree traversal is completed, we update the current OU list with the list of resolved parents.
    # 5. We now have the full parents list for an Account with the passed in OU ID. In future calls regarding this OU ID, it will reside in the resolved_parents map
    #    and will simply be returned without additional API calls necessary!
    LOGGER.debug(f"[👪] Fetching parents for OU ID: {ou_id}/{resolved_ou['Name']}...")
    returned_parents = list_parents(  # pylint: disable=no-value-for-parameter
        ChildId=ou_id, account_number=org_account_id, assume_role=assume_role, region="us-east-1"
    )
    # It only returns exactly 1 parent back out. Now, resolve the parent's parents...
    if returned_parents:
        resolved_parents[ou_id] += resolve_parents(returned_parents[0], resolved_parents, org_account_id, assume_role)

    return resolved_parents[ou_id]


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
            tag_and_parent_tasks.append(loop.run_in_executor(executor, fetch_tags_and_parent, account_id, creds, deployment_region))
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
    all_accounts: Dict[str, Any],
    resolved_parent_map: Dict[str, List[Dict[str, str]]],
    org_account_id: str,
    org_role: str,
    region_role: str,
    deployment_region: str,
) -> None:
    """
    This is the function that will go out and fetch all the additional details asynchronously with multiple spun processes. This wraps everything
    in the event loop.
    """
    loop = asyncio.new_event_loop()
    try:
        tag_and_parent_results, region_results = loop.run_until_complete(
            fetch_additional_async(loop, all_accounts, org_account_id, org_role, region_role, deployment_region)
        )
    finally:
        loop.close()

    # Merge in the tag and parent details:
    for result in tag_and_parent_results:
        all_accounts[result[0]]["Tags"] = result[1]

        # Resolve all the parents:
        parent_ous = resolve_parents(result[2][0], resolved_parent_map, org_account_id, org_role)
        all_accounts[result[0]]["Parents"] = parent_ous

    # Merge in the regions:
    for result in region_results:
        all_accounts[result[0]]["Regions"] = result[1]

    # Nothing to return because the Dictionary contents are updated by reference.
