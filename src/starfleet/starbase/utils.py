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
from yaml import YAMLError

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

    except YAMLError as exc:
        LOGGER.error(f"[❌] Invalid YAML in template: {exc}. See stacktrace for more details.")
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
        LOGGER.debug(f"[ℹ️] Processing SQS batch number: {batch_num}...")
        sqs_client.send_message_batch(QueueUrl=queue_url, Entries=batch)
