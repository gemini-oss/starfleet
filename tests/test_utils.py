"""Tests for Starfleet's utility features

This is where tests go for Starfleet's utility components, like loggers and the configuration manager to name a few.

:Module: starfleet.tests.test_utils
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
# pylint: disable=unused-argument
import json
import logging
from typing import Dict, Any

import pytest
import yaml
from botocore.client import BaseClient
from marshmallow import ValidationError

import tests
from starfleet.utils.configuration import StarfleetConfigurationLoader


def test_load_base_configuration(test_configuration: Dict[str, Any]) -> None:
    """This tests that the configuration loader is working properly."""
    # Pull some main components out and test them:
    assert test_configuration["STARFLEET"] == {
        "DeploymentRegion": "us-east-2",
        "TemplateBucket": "template-bucket",
        "FanOutQueueUrl": "https://sqs.amazonaws.com/fanout-queue",
        "AccountIndex": "TestingAccountIndexPlugin",
        "LogLevel": "DEBUG",
        "SecretsManager": {"SecretId": "starfleet-secrets", "SecretRegion": "us-east-2"},
        "ThirdPartyLoggerLevels": {
            "botocore": "CRITICAL",
            "urllib3.connectionpool": "CRITICAL",
        },
    }

    assert test_configuration["TESTING"] == {"ThisIs": "A Test"}
    assert test_configuration["SOMEOTHER"] == {"TestFile": "has been loaded properly"}


def test_configuration_exceptions() -> None:
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


def test_secret_configuration_schema() -> None:
    """This mostly just tests that we provide a proper region in to the SecretsManager part of the STARFLEET configuration."""
    from starfleet.utils.config_schema import SecretsManager

    template = """
        SecretId: starfleet-secrets
        SecretRegion: us-east-1
    """
    assert SecretsManager().load(yaml.safe_load(template))

    # With an invalid region:
    template = """
        SecretId: starfleet-secrets
        SecretRegion: pewpewpew
    """
    with pytest.raises(ValidationError) as exc:
        SecretsManager().load(yaml.safe_load(template))
    assert exc.value.messages_dict["SecretRegion"][0].startswith("Must be one of: ")


def test_load_secrets(aws_secretsmanager: BaseClient, test_configuration: Dict[str, Any]) -> None:
    """This tests out the secrets manager singleton."""
    from starfleet.utils.secrets import SecretsManager, SecretsConfigurationMissingError

    # Create the secret first:
    aws_secretsmanager.create_secret(Name="starfleet-secrets", SecretString=json.dumps({"SomeWorker": "SomeSecret"}))

    # Load the Secret:
    secrets_manager = SecretsManager()
    assert secrets_manager.secrets == {"SomeWorker": "SomeSecret"}

    # And without the configuration:
    secrets_manager._secrets = None
    test_configuration["STARFLEET"].pop("SecretsManager")
    with pytest.raises(SecretsConfigurationMissingError):
        secrets_manager.load_secrets()


def test_base_logging() -> None:
    """This tests that the base logger is configured and has the correct format."""
    from starfleet.utils.logging import LOGGER

    assert len(LOGGER.handlers) == 1
    assert LOGGER.name == "starfleet"
    assert LOGGER.handlers[0].formatter._fmt == "%(asctime)s - %(levelname)s - %(message)s - %(pathname)s - %(funcName)s:%(lineno)i"


def test_configuration_logging_levels(test_configuration: Dict[str, Any]) -> None:
    """This tests that the logger is configured properly after the configuration loads."""
    # Test that the 3rd party logger levels are configured right:
    assert logging.getLogger("botocore").level == 50  # 50 is CRITICAL
    assert logging.getLogger("urllib3.connectionpool").level == 50

    # And that ours is correct:
    assert logging.getLogger("starfleet").level == 10  # 10 is DEBUG
