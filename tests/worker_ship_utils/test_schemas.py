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

from starfleet.worker_ships.ship_schematics import WorkerShipBaseConfigurationTemplate
from starfleet.worker_ships.base_payload_schemas import (
    AccountsSpecificationSchema,
    AccountTagNameValueSchema,
    BaseAccountPayloadTemplate,
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

    # TODO: Make a fixture?
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
