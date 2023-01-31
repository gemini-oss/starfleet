"""Starfleet's logger management

This holds the Starfleet logger, which is to be used throughout the application for all logging and output purposes.

:Module: starfleet.utils.logging
:Copyright: (c) 2022 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
import logging

LOGGER = logging.getLogger("starfleet")

# Create console handler:
handler = logging.StreamHandler()

# Create formatter:
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s - %(pathname)s - %(funcName)s:%(lineno)i")

# Add formatter to the handler:
handler.setFormatter(formatter)

# Add the handler to the logger:
LOGGER.addHandler(handler)

# Documented: https://stackoverflow.com/a/50910770
LOGGER.propagate = False  # Prevents the duplicate log entries from appearing in CloudWatch Logs

# The log level will be set by the configuration.
# The configuration will also update the app's 3rd party logging levels to supress things like urllib and boto since they are noisy.
