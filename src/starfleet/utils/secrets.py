"""Starfleet's Secrets Management module

Starfleet's manager for secrets are here. This consists of a singleton class to obtain the AWS Secrets Manager secrets for this environment's execution.

:Module: starfleet.utils.secrets
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
import json
from typing import Any, Dict

import boto3

from starfleet.utils.configuration import STARFLEET_CONFIGURATION
from starfleet.utils.logging import LOGGER

# pylint: disable=pointless-string-statement
"""Mapping of the Secrets Dict:
{
    "WORKER_NAME": "Any value - this can be a string, nested Dict, etc.",
    "..."
}
"""


class SecretsConfigurationMissingError(Exception):
    """Raised if the Starfleet Configuration is missing the SecretsManager field in the STARFLEET configuration section."""


class SecretsManager:
    """This is the main Starfleet secrets management class."""

    def __init__(self):
        """Default constructor"""
        self._secrets = None

    def load_secrets(self) -> None:
        """
        This will perform the work to load the secret value from AWS Secrets manager.

        Note: If there are exceptions encountered fetching the secret, it will raise up the stack.
        """
        # Do we have a secret to manage?
        configuration = STARFLEET_CONFIGURATION.config["STARFLEET"].get("SecretsManager")
        if not configuration:
            raise SecretsConfigurationMissingError()

        LOGGER.debug(f"[🤐] Loading secrets from Secrets Manager ID in Region: {configuration['SecretId']}/{configuration['SecretRegion']}")

        client = boto3.client("secretsmanager", configuration["SecretRegion"])
        loaded = client.get_secret_value(SecretId=configuration["SecretId"])
        self._secrets = json.loads(loaded["SecretString"])
        LOGGER.debug("[🔑] Secrets loaded successfully")

    @property
    def secrets(self) -> Dict[str, Any]:
        """Fetch the Secret Dictionary. This will load the secrets if not already loaded."""
        if not self._secrets:
            self.load_secrets()

        return self._secrets


SECRETS_MANAGER = SecretsManager()
