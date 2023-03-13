"""PyTest fixtures for Starfleet's Worker Ships

This defines the PyTest fixtures that can be used by all worker ship tests.

:Module: starfleet.tests.worker_ship_utils.conftest
:Copyright: (c) 2022 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
# pylint: disable=unused-argument

from typing import Any, Dict, Generator
from unittest import mock
from unittest.mock import MagicMock

import pytest
import yaml

SAMPLE_GOOD_CONFIG = """
Enabled: False
TemplatePrefix: somePrefix/
InvocationQueueUrl: https://sqs.amazonaws.com/SomeQueueUrl
InvocationSources:
    - S3
    - EVENTBRIDGE_TIMED_EVENT
EventBridgeTimedFrequency: HOURLY
"""


SAMPLE_BASE_PAYLOAD_TEMPLATE = """
TemplateName: SampleBasePayloadTemplate
TemplateDescription: This is a template for unit test purposes only.
"""


@pytest.fixture
def sample_good_config() -> Dict[str, Any]:
    """This returns the SAMPLE_GOOD_CONFIG as a dictionary for use in testing schemas."""
    return yaml.safe_load(SAMPLE_GOOD_CONFIG)


@pytest.fixture
def sample_payload_template() -> Dict[str, Any]:
    """This returns the SAMPLE_BASE_PAYLOAD_TEMPLATE as a dictionary for use in testing schemas."""
    return yaml.safe_load(SAMPLE_BASE_PAYLOAD_TEMPLATE)


@pytest.fixture
def mock_loader_logger() -> Generator[MagicMock, None, None]:
    """This will mock out the logger that is used during the worker ship loading and return a MagicMock for tests to verify that log entries are being made."""
    with mock.patch("starfleet.worker_ships.loader.LOGGER") as mock_logger:
        yield mock_logger
