"""Tests for worker ship configuration and other schemas.

This tests all schema things related to worker ships.

:Module: starfleet.tests.worker_ship_utils.test_schemas
:Copyright: (c) 2022 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
from typing import Any, Dict

import pytest
import yaml
from marshmallow import ValidationError

from starfleet.utils.niceties import get_all_regions
from starfleet.worker_ships.ship_schematics import WorkerShipBaseConfigurationTemplate
from starfleet.worker_ships.base_payload_schemas import (
    AccountsSpecificationSchema,
    AccountTagNameValueSchema,
    BaseAccountPayloadTemplate,
    BaseAccountRegionPayloadTemplate,
    IncludeAccountsSpecificationSchema,
    WorkerShipPayloadBaseTemplate,
)


def test_base_configuration_template_schema(sample_good_config: Dict[str, Any]) -> None:
    """This tests that the base configuration template schema works properly."""
    loaded_config = WorkerShipBaseConfigurationTemplate().load(sample_good_config)
    assert WorkerShipBaseConfigurationTemplate().dump(loaded_config) == sample_good_config

    # Remove a required field:
    sample_good_config.pop("TemplatePrefix")
    with pytest.raises(ValidationError) as verr:
        WorkerShipBaseConfigurationTemplate().load(sample_good_config)
    assert verr.value.messages == {"TemplatePrefix": ["Missing data for required field."]}


def test_base_configuration_missing_eventbridge(sample_good_config: Dict[str, Any]) -> None:
    """This tests that if the base configuration is missing an EventBridge timed event frequency"""
    sample_good_config.pop("EventBridgeTimedFrequency", None)

    with pytest.raises(ValidationError) as verr:
        WorkerShipBaseConfigurationTemplate().load(sample_good_config)
    assert "A EventBridgeTimedFrequency is required when specifying an invocation event of EVENTBRIDGE_TIMED_EVENT." in str(verr)


def test_base_configuration_permits_non_specified_items(sample_good_config: Dict[str, Any]) -> None:
    """This tests that if the base configuration contains undefined fields, they are passed on through."""
    sample_good_config["SomeField"] = "SomeValue"

    loaded_config = WorkerShipBaseConfigurationTemplate().load(sample_good_config)
    assert loaded_config["SomeField"] == "SomeValue"


def test_base_payload_template_schema(sample_payload_template: Dict[str, Any]) -> None:
    """This tests that the base payload template schema works properly."""
    payload = WorkerShipPayloadBaseTemplate().load(sample_payload_template)
    assert WorkerShipPayloadBaseTemplate().dump(payload) == sample_payload_template

    # Remove a required field:
    sample_payload_template.pop("TemplateName")
    with pytest.raises(ValidationError) as verr:
        WorkerShipPayloadBaseTemplate().load(sample_payload_template)
    assert verr.value.messages == {"TemplateName": ["Missing data for required field."]}


def test_base_payload_template_permits_non_specified_items(sample_payload_template: Dict[str, Any]) -> None:
    """This tests that if the base payload template contains undefined fields, they are passed on through."""
    sample_payload_template["SomeField"] = "SomeValue"

    payload = WorkerShipPayloadBaseTemplate().load(sample_payload_template)
    assert payload["SomeField"] == "SomeValue"


def test_account_tag_schema() -> None:
    """This test that the payload schema for account tagging is correct."""
    # Good schema:
    assert not AccountTagNameValueSchema().validate({"Name": "SomeTagName", "Value": "SomeTagValue"})  # An empty error dict should be returned.

    # Bad schema:
    errors = AccountTagNameValueSchema().validate({"lol": "no", "Value": "No"})
    assert errors == {"Name": ["Missing data for required field."], "lol": ["Unknown field."]}

    # Test the validation:
    errors = AccountTagNameValueSchema().validate({"Name": "", "Value": ""})
    assert errors == {"Name": ["Length must be between 1 and 128."]}
    errors = AccountTagNameValueSchema().validate({"Name": "a" * 129, "Value": "b" * 257})
    assert errors == {"Value": ["Longer than maximum length 256."], "Name": ["Length must be between 1 and 128."]}


def test_account_specification_schemas() -> None:
    """This tests both the include/exclude account specification schemas."""
    schema = AccountsSpecificationSchema()

    # Good Schema:
    assert not schema.validate(
        {
            "ByNames": ["Account One", "Account Two"],
            "ByIds": [
                "000000000001",
                "000000000002",
                "000000000003",
            ],
            "ByOrgUnits": ["SomeOu", "SomeOtherOu", "ou-1234-12345678"],
            "ByTags": [{"Name": "Environment", "Value": "Test"}, {"Name": "Environment", "Value": "Prod"}],
        }
    )  # There should be no errors dict returned.

    # And for all accounts (IncludeAccounts schema):
    assert not IncludeAccountsSpecificationSchema().validate({"AllAccounts": True})  # There should be no errors dict returned.

    # With invalid Account Names:
    errors = schema.validate({"ByNames": ["Account One", "", "bad" * 100]})
    assert errors == {"ByNames": {1: ["Length must be between 1 and 128."], 2: ["Length must be between 1 and 128."]}}

    # With invalid Account IDs:
    errors = schema.validate({"ByIds": ["", "000000000001", "0" * 13]})
    assert errors == {"ByIds": {0: ["Length must be between 1 and 12."], 2: ["Length must be between 1 and 12."]}}

    # With invalid Org Unit IDs and Names:
    errors = schema.validate({"ByOrgUnits": ["ProperOU", "", "ou-" + "a" * 68, "a" * 200]})
    assert errors == {
        "ByOrgUnits": {1: ["Length must be greater than 0."], 2: ["Length must be less than 68 for OU IDs."], 3: ["Length must be less than 128 for OU Names."]}
    }

    # And for all accounts (IncludeAccounts schema) where AllAccounts is true, and there is another field set:
    errors = IncludeAccountsSpecificationSchema().validate({"AllAccounts": True, "ByNames": ["WRONG"]})
    assert errors == {"ByNames": ["Can't specify other parameters when `AllAccounts` is set to `True`."]}


def test_base_account_payload_template() -> None:
    """This tests the schema for the BaseAccountPayloadTemplate."""
    schema = BaseAccountPayloadTemplate()

    good_payload = """
    TemplateName: TestingPayload
    TemplateDescription: A proper payload that should be serialized properly.
    IncludeAccounts:
      AllAccounts: True
    ExcludeAccounts:
      ByNames:
        - "Some Test Account"
    """
    assert not schema.validate(yaml.safe_load(good_payload))

    good_payload_no_exclusion = """
    TemplateName: TestingPayload
    TemplateDescription: A proper payload that should be serialized properly.
    IncludeAccounts:
      AllAccounts: True
    """
    assert not schema.validate(yaml.safe_load(good_payload_no_exclusion))

    # Bad payload -- can't specify both AllAccounts and also provide an additional field
    bad_payload = """
    TemplateName: Bad Payload
    TemplateDescription: A bad payload that should not be serialized.
    IncludeAccounts:
      AllAccounts: True
      ByOrgUnits:
        - SomeOrg
    ExcludeAccounts:
      ByNames:
        - "Some Test Account"
    OperateInOrgRoot: False
    """
    errors = schema.validate(yaml.safe_load(bad_payload))
    assert errors == {"IncludeAccounts": {"ByOrgUnits": ["Can't specify other parameters when `AllAccounts` is set to `True`."]}}

    # Missing the included accounts
    bad_payload = """
    TemplateName: Bad Payload
    TemplateDescription: A bad payload that should not be serialized.
    ExcludeAccounts:
      ByNames:
        - "Some Test Account"
    OperateInOrgRoot: True
    """
    errors = schema.validate(yaml.safe_load(bad_payload))
    assert errors == {"IncludeAccounts": ["Missing data for required field."]}

    # Included accounts is an empty dictionary:
    bad_payload = """
    TemplateName: Bad Payload
    TemplateDescription: A bad payload that should not be serialized.
    IncludeAccounts: {}
    """
    errors = schema.validate(yaml.safe_load(bad_payload))
    assert errors == {
        "IncludeAccounts": {
            "AllAccounts": [
                "Missing an account field set. Either set `AllAccounts: True`, or specify an account `ByNames`, `ByIds`, `ByTags`, and/or `ByOrgUnits`."
            ],
            "ByNames": [
                "Missing an account field set. Either set `AllAccounts: True`, or specify an account `ByNames`, `ByIds`, `ByTags`, and/or `ByOrgUnits`."
            ],
            "ByIds": ["Missing an account field set. Either set `AllAccounts: True`, or specify an account `ByNames`, `ByIds`, `ByTags`, and/or `ByOrgUnits`."],
            "ByOrgUnits": [
                "Missing an account field set. Either set `AllAccounts: True`, or specify an account `ByNames`, `ByIds`, `ByTags`, and/or `ByOrgUnits`."
            ],
            "ByTags": [
                "Missing an account field set. Either set `AllAccounts: True`, or specify an account `ByNames`, `ByIds`, `ByTags`, and/or `ByOrgUnits`."
            ],
        }
    }


def test_base_account_region_payload_template() -> None:
    """This tests the schema for the BaseAccountRegionPayloadTemplate."""
    schema = BaseAccountRegionPayloadTemplate()

    all_regions = get_all_regions()
    assert len(all_regions) > 26  # As of March 2023

    good_payload_all_regions = """
    TemplateName: TestingRegionPayload
    TemplateDescription: A proper payload that should be serialized properly.
    IncludeAccounts:
      AllAccounts: True
    IncludeRegions:
      - ALL
    """
    serialized = schema.load(yaml.safe_load(good_payload_all_regions))
    assert serialized["include_regions"] == all_regions
    assert "ALL" not in serialized["include_regions"]

    good_payload_some_regions = """
    TemplateName: TestingRegionPayload
    TemplateDescription: A proper payload that should be serialized properly.
    IncludeAccounts:
      AllAccounts: True
    IncludeRegions:
      - us-east-1
      - us-east-2
    """
    assert schema.load(yaml.safe_load(good_payload_some_regions))["include_regions"] == {"us-east-1", "us-east-2"}

    good_payload_some_exclusion = """
    TemplateName: TestingPayload
    TemplateDescription: A proper payload that should be serialized properly.
    IncludeAccounts:
      AllAccounts: True
    IncludeRegions:
      - ALL
    ExcludeRegions:
      - us-west-1
      - ca-central-1
    """
    assert schema.load(yaml.safe_load(good_payload_some_exclusion))["exclude_regions"] == {"us-west-1", "ca-central-1"}

    # Bad payload -- can't specify to run in ALL regions and also note another region:
    bad_payload = """
    TemplateName: Bad Payload
    TemplateDescription: A bad payload that should not be serialized.
    IncludeAccounts:
      AllAccounts: True
    IncludeRegions:
      - us-west-1
      - ALL
      - us-east-1
    """
    errors = schema.validate(yaml.safe_load(bad_payload))
    assert errors == {"IncludeRegions": ["Can't specify any other regions when `ALL` is specified in the list."]}

    # Missing the included regions
    bad_payload = """
    TemplateName: Bad Payload
    TemplateDescription: A bad payload that should not be serialized.
    IncludeAccounts:
      AllAccounts: True
    """
    errors = schema.validate(yaml.safe_load(bad_payload))
    assert errors == {"IncludeRegions": ["Missing data for required field."]}

    # An empty list (need at least 1 region)
    bad_payload = """
    TemplateName: Bad Payload
    TemplateDescription: A bad payload that should not be serialized.
    IncludeAccounts:
      AllAccounts: True
    IncludeRegions: []
    """
    errors = schema.validate(yaml.safe_load(bad_payload))
    assert errors == {"IncludeRegions": ["Shorter than minimum length 1."]}

    # With invalid region names:
    bad_payload = """
    TemplateName: Bad Payload
    TemplateDescription: A bad payload that should not be serialized.
    IncludeAccounts:
      AllAccounts: True
    IncludeRegions:
      - us-east-1
      - fake-region
      - us-west-2
      - another-fake-region
    ExcludeRegions:
      - us-east-2
      - fake-region
      - us-west-1
      - another-fake-region
    """
    errors = schema.validate(yaml.safe_load(bad_payload))
    for bad_region in ["fake-region", "another-fake-region"]:
        assert bad_region in errors["IncludeRegions"][0]
        assert bad_region in errors["ExcludeRegions"][0]
