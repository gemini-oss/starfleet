"""Utilities unique for the Starbase

This defines utility functions for the Starbase

:Module: starfleet.starbase.utils
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
import json
from typing import Any, Dict, List, Type, Generator

import boto3
from botocore.client import BaseClient
from botocore.exceptions import ClientError
from cloudaux.aws.decorators import paginated
import yaml

from starfleet.account_index.resolvers import resolve_worker_template_accounts, resolve_worker_template_account_regions
from starfleet.utils.logging import LOGGER


@paginated("Contents", request_pagination_marker="ContinuationToken", response_pagination_marker="NextContinuationToken")
def list_objects(client: Type[BaseClient], bucket: str, prefix: str, **kwargs) -> List[Dict[str, Any]]:
    """This is a cloudaux wrapped call for boto3's list_object_v2 function to obtain all the objects from the given S3 prefix."""
    result = client.list_objects_v2(Bucket=bucket, Prefix=prefix, **kwargs)
    if not result.get("Contents"):
        result["Contents"] = []
    return result


def fetch_template(client: Type[BaseClient], bucket: str, prefix: str) -> Dict[str, Any]:
    """Fetch the template object from the bucket. This loads it as a YAML and returns it as a Dict."""
    try:
        template_blob = client.get_object(Bucket=bucket, Key=prefix)["Body"]
        return yaml.safe_load(template_blob)

    except ClientError as exc:
        if exc.response["Error"]["Code"] == "NoSuchKey":
            LOGGER.error(f"[❌] Can't find the template: {prefix} in S3. Please investigate why it's missing.")
        else:
            LOGGER.error(
                f"[❌] Some problem occurred reaching out to S3 ({exc.response['Error']['Code']}) while fetching: {prefix}. Please review the stacktrace."
            )

        raise

    except Exception as exc:
        LOGGER.error(f"[❌] Invalid YAML in template or some other problem: {exc}. See stacktrace for more details.")
        raise


def list_worker_ship_templates(bucket: str, bucket_region: str, prefix: str, worker_ship_name: str) -> List[str]:
    """This returns a list of the templates for the given worker ship in S3."""
    # Check if the template in the configuration ends in ".yaml". If it does, then just return that back. No need to do an unnecessary S3 API call.
    if prefix.endswith(".yaml"):
        return [prefix]

    # Otherwise, go to S3 and get the list of objects back out:
    LOGGER.debug(f"[🪣] Fetching the list of template objects in {bucket}/{prefix} for the {worker_ship_name} worker ship...")
    client = boto3.client("s3", region_name=bucket_region)
    keys = list_objects(client, bucket, prefix)
    template_list = [obj["Key"] for obj in keys if obj["Key"].endswith(".yaml")]
    LOGGER.debug(f"[🧮] Fetched {len(template_list)} templates for {worker_ship_name}.")

    return template_list


def get_template_batch(templates: List[str], worker_ship_name: str) -> Generator[List[str], None, None]:
    """This is a generator function that returns a batch of at most 10 items at a time."""
    start = 0
    while start < len(templates):
        batch = []
        template_batch = templates[start : start + 10]  # noqa
        for offset, template in enumerate(template_batch, 1):
            batch.append(
                {
                    "Id": str(start + offset),  # This is needed for SQS send message batch, and needs to be unique within a request.
                    "MessageBody": json.dumps({"worker_ship": worker_ship_name, "template_prefix": template}),
                }
            )
        yield batch
        start += 10


def task_starbase_fanout(templates: List[str], queue_url: str, sqs_client: BaseClient, worker_ship_name: str) -> None:
    """This will task the starbase fanout by placing batches of the templates to the Starbase Fan Out SQS queue."""
    batch_num = 1
    for batch in get_template_batch(templates, worker_ship_name):
        LOGGER.debug(f"[ℹ️] Processing SQS batch number: {batch_num} to queue: {queue_url}...")
        sqs_client.send_message_batch(QueueUrl=queue_url, Entries=batch)


def account_fanout(
    verified_template: Dict[str, Any],
    original_template: Dict[str, Any],
    template_bucket: str,
    template_prefix: str,
    queue_url: str,
    sqs_client: BaseClient,
    worker_ship_name: str,
) -> None:
    """This will perform the fan out logic for an Account worker ship."""
    accounts_to_operate_on = resolve_worker_template_accounts(verified_template)
    if not accounts_to_operate_on:
        LOGGER.error(f"[🤷‍♂️] The worker ship: {worker_ship_name}'s template at {template_bucket}/{template_prefix} has no accounts to task!")
        return

    LOGGER.info(f"[🔢] Tasking {worker_ship_name} for {len(accounts_to_operate_on)}...")
    LOGGER.debug(f"[ℹ️] Worker: {worker_ship_name} will operate on accounts: {accounts_to_operate_on}...")

    # For each account we need to send over the template to SQS:
    batch = []
    for account in accounts_to_operate_on:
        original_template["StarbaseAssignedAccount"] = account
        batch.append({"Id": account, "MessageBody": json.dumps(original_template)})

        if len(batch) == 10:
            LOGGER.debug(f"[ℹ️] Processing SQS batch to queue: {queue_url}...")
            sqs_client.send_message_batch(QueueUrl=queue_url, Entries=batch)
            batch = []

    # Send over any stragglers:
    if batch:
        LOGGER.debug(f"[ℹ️] Processing SQS batch to queue: {queue_url}...")
        sqs_client.send_message_batch(QueueUrl=queue_url, Entries=batch)


def account_region_fanout(
    verified_template: Dict[str, Any],
    original_template: Dict[str, Any],
    template_bucket: str,
    template_prefix: str,
    queue_url: str,
    sqs_client: BaseClient,
    worker_ship_name: str,
) -> None:
    """This will perform the fan out logic for an Account/Region worker ship."""
    accounts_regions_map = resolve_worker_template_account_regions(verified_template)

    # Obtain the count. This could be empty if we got no accounts to task -- or if we got no regions to task!
    total = 0
    for account, regions in accounts_regions_map.items():
        total += len(regions)
    if not total:
        LOGGER.error(f"[🤷‍♂️] The worker ship: {worker_ship_name}'s template at {template_bucket}/{template_prefix} has no accounts/regions to task!")
        return

    LOGGER.info(f"[🔢] Tasking {worker_ship_name} for {total} account/region pairs...")
    LOGGER.debug(f"[ℹ️] Worker: {worker_ship_name} will operate on account/region pairs: {accounts_regions_map}...")

    # For each account we need to send over the template to SQS:
    batch = []
    for account, regions in accounts_regions_map.items():
        original_template["StarbaseAssignedAccount"] = account

        for region in regions:
            original_template["StarbaseAssignedRegion"] = region
            batch.append({"Id": f"{account}{region}", "MessageBody": json.dumps(original_template)})

            if len(batch) == 10:
                LOGGER.debug(f"[ℹ️] Processing SQS batch to queue: {queue_url}...")
                sqs_client.send_message_batch(QueueUrl=queue_url, Entries=batch)
                batch = []

    # Send over any stragglers:
    if batch:
        LOGGER.debug(f"[ℹ️] Processing SQS batch to queue: {queue_url}...")
        sqs_client.send_message_batch(QueueUrl=queue_url, Entries=batch)
