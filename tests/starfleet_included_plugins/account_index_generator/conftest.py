"""PyTest fixtures for the Account Indexer ship

This defines the PyTest fixtures exclusively for the Account Indexer worker

:Module: starfleet.tests.worker_ship_plugins.conftest
:Copyright: (c) 2022 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""

# pylint: disable=redefined-outer-name,unused-argument,duplicate-code
import json
from datetime import datetime, UTC
from typing import Any, Dict, Generator, Optional
from unittest import mock
from unittest.mock import MagicMock

import boto3
import pytest
import yaml
from botocore.client import BaseClient
from moto import mock_aws


@pytest.fixture
def aws_s3(aws_credentials: None) -> Generator[BaseClient, None, None]:
    """This is a fixture for a Moto wrapped AWS S3 mock for the entire unit test."""
    with mock_aws():
        yield boto3.client("s3", region_name="us-east-2")  # Assuming that our deployment region for everything is us-east-2.


@pytest.fixture
def aws_ec2(aws_credentials: None) -> Generator[BaseClient, None, None]:
    """This is a fixture for a Moto wrapped AWS EC2 mock for the entire unit test."""
    with mock_aws():
        yield boto3.client("ec2", region_name="us-east-2")  # Assuming that our deployment region for everything is us-east-2.


@pytest.fixture
def inventory_bucket(aws_s3: BaseClient) -> str:
    """This is the fixture of the inventory S3 bucket. This returns the name of the bucket back out."""
    aws_s3.create_bucket(Bucket="account-inventory-s3-bucket", CreateBucketConfiguration={"LocationConstraint": "us-east-2"})
    return "account-inventory-s3-bucket"


@pytest.fixture
def good_configuration() -> Dict[str, Any]:
    """This is a sample good configuration for the Account Indexer worker ship."""
    good_config = """
        Enabled: True
        TemplatePrefix: AccountIndexWorker/
        InvocationQueueUrl: https://sqs.amazonaws.com/StarfleetAccountIndexWorker
        FanOutStrategy: SINGLE_INVOCATION
        InvocationSources:
            - S3
            - EVENTBRIDGE_TIMED_EVENT
        EventBridgeTimedFrequency: HOURLY
        OrgAccountAssumeRole: starfleet-worker-basic-test-role
        OrgAccountId: "123456789012"
        OrgRootId: r-123456
        DescribeRegionsAssumeRole: starfleet-worker-basic-test-role
    """

    return yaml.safe_load(good_config)


@pytest.fixture
def good_payload() -> Dict[str, Any]:
    """This is a sample good configuration for the Account Indexer worker ship."""
    good_payload = """
    TemplateName: StarfleetAccountIndexer
    TemplateDescription: This is a template for the Starfleet Account Indexer worker ship
    AccountInventoryBucket: account-inventory-s3-bucket
    InventoryBucketRegion: us-east-2
    """

    return yaml.safe_load(good_payload)


def account_generator(paginator: Optional[str] = None) -> Dict[str, Any]:
    """This is a function that will generate a list of at most 20 accounts for mocking out the AWS Organizations list_accounts API."""
    current_page = 0 if not paginator else int(paginator)

    if current_page > 3:
        return {"Accounts": []}

    # Return 5 at a time:
    start_index = current_page * 5
    accounts = []
    for count in range(start_index, start_index + 5):
        accounts.append(
            {
                "Id": str(count + 1).zfill(12),
                "Arn": f"arn:aws:organizations::000000000020:account/o-abcdefghi/{str(count + 1).zfill(12)}",
                "Email": f"account{count + 1}@company.com",
                "Name": f"Account {count + 1}",
                "Status": "ACTIVE",
                "JoinedMethod": "INVITED",
                "JoinedTimestamp": datetime.now(UTC),
            }
        )

    return {"Accounts": accounts, "NextToken": str(current_page + 1)}


@pytest.fixture
def mock_boto3_sts_orgs_calls() -> Generator[MagicMock, None, None]:
    """This will mock out the Organizations STS related calls so that it will return the proper responses back out"""

    def list_accounts(**kwargs) -> Dict[str, Any]:
        """This is the mocked out list_accounts call."""
        return account_generator(paginator=kwargs.pop("NextToken", None))

    unit_map = {
        "ou-1234-5678910": "SomeOU",
        "ou-1234-5678911": "SomeNestedOU",
        "ou-1234-5678912": "SomeNestedNestedOU",
    }

    def list_organizational_units_for_parent(*args, **kwargs) -> Dict[str, Any]:  # noqa
        """This is the mocked out function that will just list all the OUs that are not Root back out."""
        return {
            "OrganizationalUnits": [{"Id": "ou-1234-5678910", "Arn": "arn:aws:organizations::000000000020:ou/o-000000000020/ou-1234-5678910", "Name": "SomeOU"}]
        }

    def fetch_parent_ous_in_resolve(*args, **kwargs) -> Dict[str, Any]:  # noqa
        """This is the mocked out function that will return the parent OUs in the resolve function. This is only ever called"""
        if kwargs["ChildId"] == "ou-1234-5678912":
            return {"Parents": [{"Id": "ou-1234-5678911", "Type": "ORGANIZATIONAL_UNIT"}]}

        return {"Parents": [{"Id": "ou-1234-5678910", "Type": "ORGANIZATIONAL_UNIT"}]}

    def describe_organizational_unit(*args, **kwargs) -> Dict[str, Any]:  # noqa
        """The mocked out call to describing organizational units"""
        return {
            "OrganizationalUnit": {
                "Id": kwargs["OrganizationalUnitId"],
                "Arn": f"arn:aws:organizations::000000000020:ou/o-000000000020/{kwargs['OrganizationalUnitId']}",
                "Name": unit_map[kwargs["OrganizationalUnitId"]],
            }
        }

    # Make the "returned" magic mock. This is the mocked out boto3 client, which is returned when the boto3_cached_conn function is instantiated
    mocked_boto_client = MagicMock()
    mocked_boto_client.list_accounts = MagicMock(side_effect=list_accounts)
    mocked_boto_client.list_organizational_units_for_parent = MagicMock(side_effect=list_organizational_units_for_parent)
    mocked_boto_client.list_parents = MagicMock(side_effect=fetch_parent_ous_in_resolve)
    mocked_boto_client.describe_organizational_unit = MagicMock(side_effect=describe_organizational_unit)

    # This is the mocked boto3_cached_conn function itself. It needs to have a return_value to the mocked out client above:
    with mock.patch("cloudaux.aws.sts.boto3_cached_conn", return_value=mocked_boto_client) as mocked_cache_conn:
        yield mocked_cache_conn


@pytest.fixture
def account_map(mock_boto3_sts_orgs_calls: MagicMock) -> Dict[str, Any]:
    """The account list from the mocked call."""
    from starfleet.worker_ships.plugins.account_index_generator.utils import list_accounts, get_account_map

    return get_account_map(list_accounts(account_number="000000000020", assume_role="testing"))  # pylint: disable=no-value-for-parameter


@pytest.fixture
def mock_direct_boto_clients() -> Generator[MagicMock, None, None]:
    """
    Mocks out the direct boto3 client creator. The mocked boto3 object has a new client() function that will return the normal boto3 client (gets mocked with moto)
    for all services *except* organizations. For organizations, we're making a MagicMock that mocks out the `list_tags_for_resource` and `list_parents` call.

    Accounts 10 and 11 have nested OU residency.
    """
    old_client = boto3.client

    def fetch_tags(*args, **kwargs) -> Dict[str, Any]:  # noqa
        """This is the mocked out function that will just return a few tags out."""
        return {"Tags": [{"Key": f"Key{x}", "Value": f"Value{x}"} for x in range(1, 4)]}

    def fetch_parent_ous(*args, **kwargs) -> Dict[str, Any]:  # noqa
        """This is the mocked out function that will just return a few Org OUs back out."""
        # If the root is passed in (000000000020), then return the Root org ID:
        if kwargs["ChildId"] == "000000000020":
            return {"Parents": [{"Id": "r-123456", "Type": "ROOT"}]}

        # If account 10 is passed in (000000000010), then return the parent OU (ou-1234-5678912) - Account 10 will live in a nested OU of a nested OU
        # (SomeOU --> SomeNestedOU --> SomeNestedNestedOU --> Account10)
        if kwargs["ChildId"] == "000000000010":
            return {"Parents": [{"Id": "ou-1234-5678912", "Type": "ORGANIZATIONAL_UNIT"}]}

        # If account 11 is passed in (000000000011), then return the parent OU (ou-1234-5678911) - Account 11 will live in a nested OU of a nested OU
        # (SomeOU --> SomeNestedOU --> Account11)
        if kwargs["ChildId"] == "000000000011":
            return {"Parents": [{"Id": "ou-1234-5678911", "Type": "ORGANIZATIONAL_UNIT"}]}

        return {"Parents": [{"Id": "ou-1234-5678910", "Type": "ORGANIZATIONAL_UNIT"}]}

    class MockedBoto3:
        """This is a mocked Boto3 package that will return a normal boto3 client for everything except organizations. Moto handles the other mocked boto calls."""

        def client(self, service, **kwargs):
            """This is the mocked out client call that for organizations, will return the proper mocked out details. For others, it just returns a normal boto3 client."""
            if service == "organizations":
                mocked_client = MagicMock()
                mocked_client.list_tags_for_resource = MagicMock(side_effect=fetch_tags)
                mocked_client.list_parents = MagicMock(side_effect=fetch_parent_ous)

                return mocked_client

            # Let moto take care of the rest:
            return old_client(service, **kwargs)

    # NOTE: We also need to mock out the get_account_id_from in moto.iam.models since that causes issues with Threading. We don't need to run this function, we just need
    # to return the default account ID back from their function call, which is just 123456789012 (fixed in moto PR: 5882)
    with mock.patch("moto.iam.models.get_account_id_from", lambda x: "123456789012"):
        with mock.patch("starfleet.worker_ships.plugins.account_index_generator.utils.boto3", MockedBoto3()) as mocked_boto:
            yield mocked_boto


@pytest.fixture
def lambda_payload(good_payload: Dict[str, Any]) -> Dict[str, Any]:
    """This is the payload from SQS encoded in the Body of the dictionary. Not including the rest of the SQS details."""
    return {"Records": [{"body": json.dumps(good_payload)}]}


@pytest.fixture
def account_index_config(inventory_bucket: str, test_configuration: Dict[str, Any]) -> Dict[str, Any]:
    """This is a fixture that sets the main app's configuration to include the default account indexer's"""
    test_configuration["StarfleetDefaultAccountIndex"] = {"IndexBucket": inventory_bucket, "BucketRegion": "us-east-2"}

    return test_configuration


@pytest.fixture
def index_obj(account_index_config: Dict[str, Any], aws_s3: BaseClient, inventory_bucket: str) -> Dict[str, Any]:
    """
    This will load a pre-generated test Account Index JSON file named generatedIndex.json. This is mock uploaded to S3.
    This file should be kept up to date with any changes that are made to the AccountIndexGeneratorShip
    """
    import tests.starfleet_included_plugins.account_index_generator

    path = f"{tests.starfleet_included_plugins.account_index_generator.__path__[0]}/generatedIndex.json"

    with open(path, "r", encoding="utf-8") as file:
        file_text = file.read()
    aws_s3.put_object(Bucket=inventory_bucket, Key="accountIndex.json", Body=file_text)

    return json.loads(file_text)
