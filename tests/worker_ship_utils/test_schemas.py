"""Tests for worker ship configuration and other schemas.

This tests all schema things related to worker ships.

:Module: starfleet.tests.worker_ship_utils.test_schemas
:Copyright: (c) 2022 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
from typing import Any, Dict

import pytest
from marshmallow import ValidationError

from starfleet.worker_ships.ship_schematics import WorkerShipBaseConfigurationTemplate, WorkerShipPayloadBaseTemplate


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
