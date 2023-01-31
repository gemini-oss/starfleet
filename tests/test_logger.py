"""Tests for Starfleet's logging capabilities.

Verifies that the utils loader works properly.

:Module: starfleet.tests.test_logger
:Copyright: (c) 2022 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
# pylint: disable=unused-argument

import logging
from typing import Any, Dict


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
