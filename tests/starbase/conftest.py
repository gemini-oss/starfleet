"""PyTest fixtures for Starfleet's Starbase

This defines the PyTest fixtures for the Starbase tests

:Module: starfleet.tests.starbase.conftest
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
import json

# pylint: disable=unused-argument,redefined-outer-name
from typing import Generator, Set, Any, Dict
from unittest import mock

import boto3
import pytest
from botocore.client import BaseClient
from moto import mock_s3, mock_sqs

from starfleet.account_index.schematics import AccountIndexInstance
from starfleet.worker_ships.base_payload_schemas import BaseAccountPayloadTemplate, BaseAccountRegionPayloadTemplate
from starfleet.worker_ships.loader import StarfleetWorkerShipLoader


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
def test_index(test_configuration: Dict[str, Any]) -> Generator[AccountIndexInstance, None, None]:
    """This returns the StarfleetAccountIndexLoader with a TestingAccountIndexPlugin mocked out for it. This mocks out for the entire app."""
    from starfleet.account_index.loader import ACCOUNT_INDEX, StarfleetAccountIndexLoader
    import tests.account_index.testing_plugins

    account_indexer = StarfleetAccountIndexLoader()
    account_indexer._index_ship_path = tests.account_index.testing_plugins.__path__
    account_indexer._index_ship_prefix = tests.account_index.testing_plugins.__name__ + "."

    # Just mock out the index. The singleton function will simply return the populated index attribute:
    ACCOUNT_INDEX._index = account_indexer.index
    yield ACCOUNT_INDEX.index
    ACCOUNT_INDEX.reset()


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
def single_payload_templates(aws_s3: BaseClient, template_bucket: str) -> Set[str]:
    """These are the single invocation template YAMLs that are uploaded to the mock template bucket for a test worker."""
    encoded_template = """
    TemplateName: TestWorkerTemplate
    TemplateDescription: This is a template used for testing the Starbase
    """
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
def worker_ships(test_worker_ship_loader: StarfleetWorkerShipLoader) -> Generator[StarfleetWorkerShipLoader, None, None]:
    """This mocks out the worker ship loader for the starbase (for single invocation workers)."""
    with mock.patch("starfleet.starbase.main.STARFLEET_WORKER_SHIPS", test_worker_ship_loader) as mocked_loader:
        yield mocked_loader


@pytest.fixture
def account_worker_ships(worker_ships: StarfleetWorkerShipLoader) -> StarfleetWorkerShipLoader:
    """This is a fixture that prepares the worker ship loader for account ships and loads them."""
    from starfleet.worker_ships.ship_schematics import FanOutStrategy

    ship = worker_ships.get_worker_ships()["TestingStarfleetWorkerPlugin"]
    ship.fan_out_strategy = FanOutStrategy.ACCOUNT
    ship.payload_template_class = BaseAccountPayloadTemplate

    return worker_ships


@pytest.fixture
def account_region_worker_ships(worker_ships: StarfleetWorkerShipLoader) -> StarfleetWorkerShipLoader:
    """This is a fixture that prepares the worker ship loader for account/region ships and loads them."""
    from starfleet.worker_ships.ship_schematics import FanOutStrategy

    ship = worker_ships.get_worker_ships()["TestingStarfleetWorkerPlugin"]
    ship.fan_out_strategy = FanOutStrategy.ACCOUNT_REGION
    ship.payload_template_class = BaseAccountRegionPayloadTemplate

    return worker_ships


@pytest.fixture
def account_payload_templates(aws_s3: BaseClient, template_bucket: str) -> Set[str]:
    """
    These are the account invocation template YAMLs that are uploaded to the mock template bucket for a test worker.

    For now this just returns 1 template and also returns a set to be similar to the single_account_payload_templates fixture.
    """
    encoded_template = """
    TemplateName: TestWorkerTemplate
    TemplateDescription: This is a template used for testing the Starbase for Account workers
    IncludeAccounts:
        AllAccounts: True
    ExcludeAccounts:
        ByNames:
            - Account 1
    """.encode(
        "utf-8"
    )
    aws_s3.put_object(Bucket=template_bucket, Key="TestingStarfleetWorkerPlugin/template1.yaml", Body=encoded_template)

    return {"TestingStarfleetWorkerPlugin/template1.yaml"}


@pytest.fixture
def account_region_payload_templates(aws_s3: BaseClient, template_bucket: str) -> Set[str]:
    """
    These are the account/region invocation template YAMLs that are uploaded to the mock template bucket for a test worker.

    For now this just returns 1 template and also returns a set to be similar to the single_account_payload_templates fixture.
    """
    encoded_template = """
    TemplateName: TestWorkerTemplate
    TemplateDescription: This is a template used for testing the Starbase for Account workers
    IncludeAccounts:
        ByNames:
            - Account 1
            - Account 2
            - Account 3
            - Account 4
            - Account 5
    ExcludeAccounts:
        ByNames:
            - Account 1
    IncludeRegions:
        - us-west-1
        - us-east-1
        - us-east-2
        - eu-west-1
        - ca-central-1
    ExcludeRegions:
        - us-west-1
    """.encode(
        "utf-8"
    )
    aws_s3.put_object(Bucket=template_bucket, Key="TestingStarfleetWorkerPlugin/template1.yaml", Body=encoded_template)

    return {"TestingStarfleetWorkerPlugin/template1.yaml"}


@pytest.fixture
def fanout_lambda_payload() -> Dict[str, Any]:
    """This is the payload from SQS encoded in the Body of the dictionary. Not including the rest of the SQS details."""
    return {"Records": [{"body": '{"worker_ship": "TestingStarfleetWorkerPlugin", "template_prefix": "TestingStarfleetWorkerPlugin/template1.yaml"}'}]}


@pytest.fixture
def fanout_lambda_s3_payload() -> Dict[str, Any]:
    """This is the payload from S3 to SQS encoded in the Body of the dictionary. Not including the rest of the S3 and SQS details."""
    return {
        "Records": [
            {
                "body": json.dumps(
                    {
                        "Records": [
                            {
                                "eventSource": "aws:s3",
                                "s3": {"bucket": {"name": "template-bucket"}, "object": {"key": "TestingStarfleetWorkerPlugin/template1.yaml"}},
                            }
                        ]
                    }
                )
            }
        ]
    }
