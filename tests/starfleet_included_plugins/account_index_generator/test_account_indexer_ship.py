"""Tests for the Account Indexer ship

This defines all the tests used by the Account Indexer ship

:Module: starfleet.tests.worker_ship_plugins.account_index_generator.test_account_indexer_ship
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
# pylint: disable=unused-argument,too-many-locals
import os

from datetime import datetime
import json
from typing import Any, Dict
from unittest import mock
from unittest.mock import MagicMock

import pytest
from botocore.client import BaseClient
from click.testing import CliRunner
from marshmallow import ValidationError

from starfleet.worker_ships.loader import StarfleetWorkerShipLoader


def test_configuration_schema(good_configuration: Dict[str, Any]) -> None:
    """This tests that the config schema loads properly."""
    from starfleet.worker_ships.plugins.account_index_generator.ship import AccountIndexGeneratorShipConfigurationTemplate

    config = AccountIndexGeneratorShipConfigurationTemplate().load(good_configuration)
    assert config["org_account_assume_role"] == "starfleet-worker-basic-test-role"

    # Remove a required field:
    good_configuration.pop("OrgAccountId")
    with pytest.raises(ValidationError):
        AccountIndexGeneratorShipConfigurationTemplate().load(good_configuration)


def test_payload_schema(good_payload: Dict[str, Any]) -> None:
    """This tests that the payload schema loads properly."""
    from starfleet.worker_ships.plugins.account_index_generator.ship import AccountIndexGeneratorShip, AccountIndexGeneratorShipPayloadTemplate

    payload = AccountIndexGeneratorShipPayloadTemplate().load(good_payload)
    assert payload["account_inventory_bucket"] == "account-inventory-s3-bucket"

    # Test that the plugin can load it (and that the ships load function works properly):
    ship = AccountIndexGeneratorShip()
    ship.load_template(good_payload)
    assert ship.payload == payload

    # Remove a required field:
    good_payload.pop("InventoryBucketRegion")
    with pytest.raises(ValidationError):
        AccountIndexGeneratorShipPayloadTemplate().load(good_payload)


def test_list_org_accounts(mock_list_account: MagicMock) -> None:
    """This mostly tests that our code will pull out the proper (mocked) results from the AWS API. This also ensures that our fixture is working properly."""
    from starfleet.worker_ships.plugins.account_index_generator.utils import list_accounts

    all_accounts = list_accounts(account_number="000000000020", assume_role="testing")  # pylint: disable=no-value-for-parameter

    # Verify that we got it all:
    assert len(all_accounts) == 20
    for count in range(0, 20):
        assert isinstance(all_accounts[count].pop("JoinedTimestamp"), datetime)
        test_value = {
            "Id": f"{str(count + 1).zfill(12)}",
            "Arn": f"arn:aws:organizations::000000000020:account/o-abcdefghi/{str(count + 1).zfill(12)}",
            "Email": f"account{count + 1}@company.com",
            "Name": f"Account {count + 1}",
            "Status": "ACTIVE",
            "JoinedMethod": "INVITED",
        }
        assert all_accounts[count] == test_value


def test_get_account_map(account_map: Dict[str, Any]) -> None:
    """This is a test to ensure that we can fetch all the additional details about. This mostly just tests the fixture."""
    for account_id, account_blob in account_map.items():
        assert account_id == account_blob["Id"]


def test_fetch_additional_details(
    aws_ec2: BaseClient,
    aws_sts: BaseClient,
    account_map: Dict[str, Any],
    mock_direct_boto_clients: MagicMock,
    test_worker_ship_loader: StarfleetWorkerShipLoader,
) -> None:
    """This is a test to ensure that we can fetch all the additional details about"""
    from starfleet.worker_ships.plugins.account_index_generator.utils import fetch_additional_details

    ous = {"ou-1234-5678910": "SomeOU", "r-123456": "ROOT"}

    fetch_additional_details(account_map, ous, "r-123456", "000000000020", "testing", "testing", "us-east-2")

    # Verify that everything is there:
    tag_value = {f"Key{x}": f"Value{x}" for x in range(1, 4)}
    regions = sorted([region["RegionName"] for region in aws_ec2.describe_regions()["Regions"]])
    assert regions  # Make sure we actually have some regions
    assert "us-east-1" in regions  # Another check...
    for account in account_map.values():
        assert account["Tags"] == tag_value
        assert account["Regions"] == regions

        # And the parent OUs:
        if account["Id"] != "000000000020":
            assert account["Parents"] == [
                {"Id": "ou-1234-5678910", "Type": "ORGANIZATIONAL_UNIT", "Name": "SomeOU"},
                {"Id": "r-123456", "Type": "ROOT", "Name": "ROOT"},
            ]
        else:
            assert account["Parents"] == [{"Id": "r-123456", "Type": "ROOT", "Name": "ROOT"}]


def test_async_exceptions(aws_sts: BaseClient) -> None:
    """This tests that we can handle exceptions right if there are async issues."""
    from starfleet.worker_ships.plugins.account_index_generator.utils import AccountIndexerProcessError, fetch_additional_details

    def raise_exception(*args, **kwargs) -> None:  # noqa
        """Just a function that will raise an exception to test that we properly catch AccountIndexerProcessErrors"""
        raise Exception("Testing")  # pylint: disable=broad-exception-raised

    # Just mock with lambda functions. These can't be pickled and cause an exception.
    with pytest.raises(AccountIndexerProcessError) as exc:
        with mock.patch("starfleet.worker_ships.plugins.account_index_generator.utils.fetch_tags_and_parents", raise_exception):
            with mock.patch("starfleet.worker_ships.plugins.account_index_generator.utils.fetch_regions", raise_exception):
                fetch_additional_details({"000000000000": {}}, {"r-123456": "ROOT"}, "r-123456", "000000000020", "testing", "testing", "us-east-2")

    assert "Fetching tags and regions" in str(exc.value)


@pytest.mark.parametrize("commit", [False, True])
@pytest.mark.parametrize("cli", [False, True])
def test_full_run(
    commit: bool,
    cli: bool,
    aws_ec2: BaseClient,
    aws_s3: BaseClient,
    aws_sts: BaseClient,
    inventory_bucket: str,
    mock_list_parent_ous: None,
    account_map: Dict[str, Any],
    mock_direct_boto_clients: MagicMock,
    lambda_payload: Dict[str, Any],
    test_worker_ship_loader: StarfleetWorkerShipLoader,
) -> None:
    """This performs the full test run of the worker for both the CLI and also the Lambda."""
    from starfleet.worker_ships.plugins.account_index_generator.ship import account_inventory, lambda_handler
    from starfleet.worker_ships.plugins.account_index_generator.utils import fetch_additional_details

    # We need to get the proper account map so we can verify that we generated the proper thing:
    ou_map = {"ou-1234-5678910": "SomeOU", "r-123456": "ROOT"}
    fetch_additional_details(account_map, ou_map, "r-123456", "000000000020", "testing", "testing", "us-east-2")

    with mock.patch("starfleet.worker_ships.plugins.account_index_generator.ship.LOGGER") as mocked_logger:
        if cli:
            runner = CliRunner()
            payload_file = __file__.split("test_account_indexer_ship.py", maxsplit=1)[0] + "test_payload.yaml"
            cmd_line_args = ["generate", "--payload", payload_file]

            if commit:
                cmd_line_args.append("--commit")

            runner.invoke(account_inventory, cmd_line_args)  # noqa

        else:
            if commit:
                os.environ["STARFLEET_COMMIT"] = "true"

            lambda_handler(lambda_payload, object())  # pylint: disable=no-value-for-parameter

    if commit:
        # Verify that we got what we needed from S3:
        loaded_index = json.loads(aws_s3.get_object(Bucket=inventory_bucket, Key="accountIndex.json")["Body"].read())
        assert datetime.strptime(loaded_index["generated"], "%Y-%m-%dT%H:%M:%SZ")
        account_index = loaded_index["accounts"]

        # Pop out the timestamps from both:
        for account in list(account_index.values()) + list(account_map.values()):
            account.pop("JoinedTimestamp")

        assert account_index == account_map

    else:
        # Nothing should be in S3:
        assert not aws_s3.list_objects_v2(Bucket=inventory_bucket)["KeyCount"]

        # Verify that we just output the details (it will be the last log entry):
        log_index = (
            len(mocked_logger.info.call_args_list) - 2
        )  # Subtract 1 because it's a list, and also subtract one because of the `DONE` / Completed comment.
        assert mocked_logger.info.call_args_list[log_index].args[0].startswith("[🍣] Raw Inventory:\n")
        raw_json = mocked_logger.info.call_args_list[log_index].args[0].split("[🍣] Raw Inventory:\n")[1]
        account_index = json.loads(raw_json)

        # Pop out the timestamps from both:
        for account in list(account_index.values()) + list(account_map.values()):
            account.pop("JoinedTimestamp")

        # Verify that the output inventory JSON is exactly what it's supposed to be:
        assert account_index == account_map

    # Clean up the env var:
    os.environ.pop("STARFLEET_COMMIT", None)
