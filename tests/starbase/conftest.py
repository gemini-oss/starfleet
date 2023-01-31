"""PyTest fixtures for Starfleet's Starbase

This defines the PyTest fixtures for the Starbase tests

:Module: starfleet.tests.starbase.conftest
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
# pylint: disable=unused-argument,redefined-outer-name
from typing import Generator, Set, Any, Dict
from unittest import mock
from unittest.mock import MagicMock

import boto3
import pytest
from botocore.client import BaseClient
from moto import mock_s3, mock_sqs

from starfleet.worker_ships.loader import StarfleetWorkerShipLoader

TEST_WORKER_TEMPLATE = """
TemplateName: TestWorkerTemplate
TemplateDescription: This is a template used for testing the Starbase
"""


@pytest.fixture
def aws_s3(aws_credentials: None) -> Generator[BaseClient, None, None]:
    """This is a fixture for a Moto wrapped AWS S3 mock for the entire unit test."""
    with mock_s3():
        client = boto3.client("s3", "us-east-2")  # Assuming that our deployment region for everything is us-east-2.
        yield client


@pytest.fixture
def aws_sqs(aws_credentials: None) -> Generator[BaseClient, None, None]:
    """This is a fixture for a Moto wrapped AWS SQS mock for the entire unit test."""
    with mock_sqs():
        client = boto3.client("sqs", "us-east-2")
        yield client


@pytest.fixture
def template_bucket(aws_s3: BaseClient) -> str:
    """This will create the template bucket."""
    aws_s3.create_bucket(Bucket="template-bucket", CreateBucketConfiguration={"LocationConstraint": "us-east-2"})
    return "template-bucket"


@pytest.fixture
def fanout_queue(aws_sqs: BaseClient) -> str:
    """The fanout SQS queue for the Starbase. This returns the Queue URL back out."""
    return aws_sqs.create_queue(QueueName="fanout-queue")["QueueUrl"]


@pytest.fixture
def worker_queue(aws_sqs: BaseClient) -> str:
    """This creates the worker SQS queue and returns the Queue URL back out."""
    return aws_sqs.create_queue(QueueName="WorkerQueue1")["QueueUrl"]


@pytest.fixture
def payload_templates(aws_s3: BaseClient, template_bucket: str) -> Set[str]:
    """These are the template YAMLs that are uploaded to the mock template bucket for a test worker."""
    encoded_template = TEST_WORKER_TEMPLATE.encode("utf-8")
    templates = set()
    for plugin_prefix in ["TestingStarfleetWorkerPlugin", "TestingStarfleetWorkerPluginTwo", "TestingStarfleetWorkerPluginThree"]:
        for template_count in range(1, 3):
            aws_s3.put_object(Bucket=template_bucket, Key=f"{plugin_prefix}/template{template_count}.yaml", Body=encoded_template)
            templates.add(f"{plugin_prefix}/template{template_count}.yaml")

    return templates


@pytest.fixture
def timed_event() -> Dict[str, Any]:
    """This is an EventBridge timed event"""
    return {"name": "HOURLY"}


@pytest.fixture
def worker_ships(test_worker_ship_loader: StarfleetWorkerShipLoader) -> MagicMock:
    """This mocks out the worker ship loader for the starbase."""
    with mock.patch("starfleet.starbase.main.STARFLEET_WORKER_SHIPS", test_worker_ship_loader) as mocked_loader:
        yield mocked_loader


@pytest.fixture
def fanout_lambda_payload() -> Dict[str, Any]:
    """This is the payload from SQS encoded in the Body of the dictionary. Not including the rest of the SQS details."""
    return {"Records": [{"body": '{"worker_ship": "TestingStarfleetWorkerPlugin", "template_prefix": "TestingStarfleetWorkerPlugin/template1.yaml"}'}]}
