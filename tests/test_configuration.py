"""Tests for Starfleet's configuration loader

Verifies that the configuration loader works properly.

:Module: starfleet.tests.test_configuration
:Copyright: (c) 2022 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
from typing import Any, Dict

import pytest

from starfleet.utils.configuration import StarfleetConfigurationLoader

import tests


def test_load_base_configuration(test_configuration: Dict[str, Any]) -> None:
    """This tests that the configuration loader is working properly."""
    # Pull some main components out and test them:
    assert test_configuration["STARFLEET"] == {
        "DeploymentRegion": "us-east-2",
        "TemplateBucket": "template-bucket",
        "FanOutQueueUrl": "https://sqs.amazonaws.com/fanout-queue",
        "LogLevel": "DEBUG",
        "ThirdPartyLoggerLevels": {
            "botocore": "CRITICAL",
            "urllib3.connectionpool": "CRITICAL",
        },
    }

    assert test_configuration["TESTING"] == {"ThisIs": "A Test"}
    assert test_configuration["SOMEOTHER"] == {"TestFile": "has been loaded properly"}


def test_exceptions() -> None:
    """This tests that the exceptions are properly raised."""
    from starfleet.utils.configuration import BadConfigurationError

    config_loader = StarfleetConfigurationLoader()

    # First test is to try it without a proper directory path:
    config_loader._configuration_path = "LOLNO"

    with pytest.raises(Exception) as exc:
        config_loader.load_base_configuration()

    assert exc.typename == "FileNotFoundError"

    # Next, let's load a configuration that's missing the required sections:
    config_loader._configuration_path = f"{tests.__path__[0]}/bad_configuration_files"

    with pytest.raises(BadConfigurationError) as exc:
        config_loader.load_base_configuration()

    assert exc.value.args[0] == {"STARFLEET": ["Missing data for required field."]}
