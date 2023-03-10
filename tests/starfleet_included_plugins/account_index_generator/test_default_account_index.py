"""Tests for the Default Account Index - which uses the AccountIndexGeneratorShip's generated index.

This defines all the tests used by the Default Account Index

:Module: starfleet.tests.worker_ship_plugins.account_index_generator.test_account_indexer_ship
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
# pylint: disable=unused-argument,too-many-locals
from typing import Any, Dict

import pytest
from botocore.client import BaseClient
from botocore.exceptions import ClientError
from marshmallow import ValidationError

from starfleet.account_index.plugins.starfleet_default_index.ship import StarfleetDefaultAccountIndex


def test_missing_index_config(test_configuration: Dict[str, Any]) -> None:
    """This tests that we check for a missing index configuration"""
    from starfleet.account_index.plugins.starfleet_default_index.ship import MissingConfigurationError

    with pytest.raises(MissingConfigurationError):
        StarfleetDefaultAccountIndex()


def test_invalid_configuration(account_index_config: Dict[str, Any]) -> None:
    """This tests that we check for an invalid configuration."""
    # Remove a required field:
    account_index_config["StarfleetDefaultAccountIndex"].pop("IndexBucket")

    with pytest.raises(ValidationError) as verr:
        StarfleetDefaultAccountIndex()
    assert verr.value.messages_dict == {"IndexBucket": ["Missing data for required field."]}


def test_missing_s3_object(account_index_config: Dict[str, Any]) -> None:
    """This tests that we handle missing S3 objects."""
    with pytest.raises(ClientError) as cerr:
        StarfleetDefaultAccountIndex()
    assert cerr.typename == "NoSuchKey"


def test_invalid_json(account_index_config: Dict[str, Any], aws_s3: BaseClient, inventory_bucket: str) -> None:
    """This tests that we naively handle an improper JSON index."""
    aws_s3.put_object(Bucket=inventory_bucket, Key="accountIndex.json", Body=b"a")

    with pytest.raises(Exception) as exc:
        StarfleetDefaultAccountIndex()
    assert str(exc.value) == "Expecting value: line 1 column 1 (char 0)"


def test_loading(account_index_config: Dict[str, Any], aws_s3: BaseClient, inventory_bucket: str, index_obj: Dict[str, Any]) -> None:
    """This tests that the index can be successfully loaded and that the index_obj fixture works."""
    index = StarfleetDefaultAccountIndex()
    assert len(index.account_ids) == len(index_obj.keys())
    assert len(index.alias_map) == len(index_obj.keys())
    assert index.alias_map["Account 20".lower()] == "000000000020"
    for region_mapping in index.regions_map.values():
        assert len(region_mapping) == len(index_obj.keys())

    assert len(index.ou_map["r-123456"]) == len(index.ou_map["ROOT".lower()]) == len(index_obj.keys())
    assert len(index.ou_map["ou-1234-5678910"]) == len(index.ou_map["SomeOU".lower()]) == len(index_obj.keys()) - 1

    for tag_values in index.tag_map.values():
        for values in tag_values.values():
            assert len(values) == len(index_obj.keys())


def test_get_accounts_by_id(index_obj: Dict[str, Any]) -> None:
    """This tests getting accounts by account ID."""
    index = StarfleetDefaultAccountIndex()
    accounts = index.get_accounts_by_ids({"000000000019", "000000000020", "000000000023"})  # Also include an account that doesn't exist (23)
    assert accounts == {"000000000019", "000000000020"}


def test_get_accounts_by_alias(index_obj: Dict[str, Any]) -> None:
    """This tests getting accounts by account aliases."""
    index = StarfleetDefaultAccountIndex()
    accounts = index.get_accounts_by_aliases(
        {"Account 1", "Account 2", "AcCoUNt 3", "not an account"}
    )  # Also include an accounts that doesn't exist and odd casing
    assert accounts == {"000000000001", "000000000002", "000000000003"}


def test_get_accounts_by_tag(index_obj: Dict[str, Any]) -> None:
    """This tests getting accounts by account tags"""
    index = StarfleetDefaultAccountIndex()
    accounts = index.get_accounts_by_tag("kEy1", "VaLuE1")  # This tests casing as well
    assert len(accounts) == len(index_obj.keys())

    # With accounts that don't exist:
    assert not index.get_accounts_by_tag("fake", "tag")


def test_get_accounts_by_ou(index_obj: Dict[str, Any]) -> None:
    """This tests getting accounts by OUs"""
    index = StarfleetDefaultAccountIndex()
    accounts = index.get_accounts_by_ou("sOMeOu")  # This tests casing as well
    assert len(accounts) == len(index_obj.keys()) - 1
    assert "000000000020" not in accounts  # We didn't search for Root

    # Try this again, but this time pass in the OU ID. It should be the same result:
    assert index.get_accounts_by_ou("oU-1234-5678910") == accounts  # Also test casing


def test_get_accounts_by_regions(index_obj: Dict[str, Any]) -> None:
    """This tests getting accounts by regions"""
    index = StarfleetDefaultAccountIndex()
    regions_map = index.get_accounts_by_regions({"us-east-1", "us-east-2", "fake-region"})  # include a region that doesn't exist
    assert len(regions_map["fake-region"]) == 0
    assert len(regions_map) == 3  # it will include the empty set for fake-region
    assert len(regions_map["us-east-1"]) == len(regions_map["us-east-2"]) == len(index_obj.keys())

    # Now try getting all the regions:
    all_regions_map = index.get_accounts_for_all_regions()
    assert len(all_regions_map.keys()) > 10  # There are a bunch of regions...
    for accounts in all_regions_map.values():
        assert len(accounts) == len(index_obj.keys())


def test_get_all_accounts(index_obj: Dict[str, Any]) -> None:
    """This tests getting all accounts back"""
    index = StarfleetDefaultAccountIndex()
    accounts = index.get_all_accounts()
    assert len(accounts) == len(index_obj.keys())


def test_get_org_roots(index_obj: Dict[str, Any]) -> None:
    """This tests getting the set of Organization Roots."""
    index = StarfleetDefaultAccountIndex()
    accounts = index.get_org_roots()
    assert accounts == {"000000000020"}
