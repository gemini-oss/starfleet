"""Starfleet's configuration loader and manager

This makes use of YAML files in a very simple, but naive manner. This will simply load all YAML files into a dictionary that is used throughout the application.

:Module: starfleet.utils.configuration
:Copyright: (c) 2022 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""

import logging
import os
from typing import Any, Dict

import yaml

from starfleet.utils.config_schema import BaseConfigurationSchema
from starfleet.utils.logging import LOGGER
import starfleet

CONFIGURATION_FILE_DIR_NAME = "configuration_files"
PRE_LOGGER_LEVEL = os.environ.get("PRE_LOGGER_LEVEL", "DEBUG")


class BadConfigurationError(Exception):
    """Exception for bad Starfleet configuration"""


class StarfleetConfigurationLoader:
    """Class that loads Starfleet configuration files."""

    # Defined here for testability purposes:
    _configuration_path = f"{starfleet.__path__[0]}/{CONFIGURATION_FILE_DIR_NAME}"

    def __init__(self):
        self._app_config: Dict[str, Any] = None  # noqa

    def load_base_configuration(self) -> None:
        """This will load the base configuration for the application."""
        self._app_config = {}

        # Set up the pre-logger, which is a logger that exists before we have a proper logger set up as we have not yet loaded a configuration!
        LOGGER.setLevel(PRE_LOGGER_LEVEL)
        LOGGER.debug(f"[📄] Loading the base configuration from {self._configuration_path}...")

        # This will load all files that end in .yaml from the starfleet/configuration_files/ path:
        try:
            for file in os.listdir(self._configuration_path):
                if file.endswith(".yaml"):
                    LOGGER.debug(f"[⚙️] Processing configuration file: {file}...")

                    with open(f"{self._configuration_path}/{file}", "r", encoding="utf-8") as stream:
                        loaded = yaml.safe_load(stream)

                    self._app_config.update(loaded)

                    LOGGER.debug(f"[⚙️] Successfully loaded configuration file: {file}")

        except Exception as exc:
            LOGGER.error("[💥] Major error encountered loading configuration. Cannot proceed.")
            LOGGER.exception(exc)
            raise

        # Verify that the required components are in the configuration:
        try:
            errors = BaseConfigurationSchema().validate(self._app_config)
            if errors:
                raise BadConfigurationError(errors)

        except BadConfigurationError as bce:
            LOGGER.error("[💥] The Starfleet configuration is invalid. See the stacktrace for more details.")
            LOGGER.exception(bce)
            raise

        LOGGER.debug("[🪵] Configuring the logger for the rest of the application...")

        # Now, configure the logger from the loaded configuration:
        LOGGER.setLevel(self._app_config["STARFLEET"].get("LogLevel", PRE_LOGGER_LEVEL))

        # Update the third_party_logger_levels if specified:
        for logger_name, level in self._app_config["STARFLEET"].get("ThirdPartyLoggerLevels", {}).items():
            logging.getLogger(logger_name).setLevel(level)

        LOGGER.debug("[🆗️] Base configuration loaded successfully")

    @property
    def config(self) -> Dict[str, Any]:
        """Lazy-loads the application configuration. If not already loaded it will load the base configuration and then return it."""
        if not self._app_config:
            self.load_base_configuration()

        return self._app_config


STARFLEET_CONFIGURATION = StarfleetConfigurationLoader()
