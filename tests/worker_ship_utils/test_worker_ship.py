"""Tests the worker ship plugin base classes and loaders.

:Module: starfleet.tests.worker_ship_utils.test_worker_ship
:Copyright: (c) 2022 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""

# pylint: disable=unused-argument

from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from starfleet.worker_ships.loader import StarfleetWorkerShipLoader


def verify_logger(mocked: MagicMock, log_entry: str) -> bool:
    """Utility function to verify that a given log entry appeared in the mocked logger calls."""
    found = False
    for log_call in mocked.method_calls:
        if str(log_call.args[0]) == log_entry:
            found = True
            break

    return found


def test_basic_plugin_template_loading(sample_payload_template: Dict[str, Any]) -> None:
    """This tests that the base class's plugin loading logic works properly (this is using the basic plugin unit test worker class to do it)"""
    from tests.worker_ship_utils.testing_plugins.basic_plugin import TestingStarfleetWorkerPlugin

    worker_ship = TestingStarfleetWorkerPlugin()

    worker_ship.load_template(sample_payload_template)
    assert worker_ship.payload == {"template_name": "SampleBasePayloadTemplate", "template_description": "This is a template for unit test purposes only."}


def test_good_plugin_loader(mock_loader_logger: MagicMock, test_configuration: Dict[str, Any], test_worker_ship_loader: StarfleetWorkerShipLoader) -> None:
    """This tests that the Starfleet worker plugin loader works properly"""
    from starfleet.worker_ships.ship_schematics import StarfleetWorkerShip

    # Check that it's in the configuration:
    worker_ships = test_worker_ship_loader.get_worker_ships()

    # Verify that the worker ships are loaded:
    assert len(worker_ships) == 3
    assert isinstance(worker_ships["TestingStarfleetWorkerPlugin"], StarfleetWorkerShip)
    assert verify_logger(mock_loader_logger, "[🚀] Completed loading 3 worker ships")


def test_plugin_loader_with_disabled_plugins(
    mock_loader_logger: MagicMock, test_configuration: Dict[str, Any], test_worker_ship_loader: StarfleetWorkerShipLoader
) -> None:
    """This tests that the Starfleet worker plugin loader works properly - with disabled workers"""
    # Disable the worker by configuration:
    test_configuration.pop("TestingStarfleetWorkerPluginTwo")
    test_configuration.pop("TestingStarfleetWorkerPluginThree")
    test_configuration["TestingStarfleetWorkerPlugin"]["Enabled"] = False
    worker_ships = test_worker_ship_loader.get_worker_ships()
    assert not worker_ships
    assert verify_logger(mock_loader_logger, "[⏭️] Worker ship: TestingStarfleetWorkerPlugin is DISABLED in it's configuration. Skipping...")
    assert verify_logger(mock_loader_logger, "[🤷] There were no properly enabled worker ships to load")

    # Remove it outright:
    mock_loader_logger.reset_mock()
    test_configuration.pop("TestingStarfleetWorkerPlugin")
    test_worker_ship_loader.reset()
    worker_ships = test_worker_ship_loader.get_worker_ships()
    assert not worker_ships
    assert verify_logger(mock_loader_logger, "[⏭️] Worker ship: TestingStarfleetWorkerPlugin has no discovered configuration. Skipping... ")
    assert verify_logger(mock_loader_logger, "[🤷] There were no properly enabled worker ships to load")


def test_plugin_loader_invalid_configuration(
    mock_loader_logger: MagicMock, test_configuration: Dict[str, Any], test_worker_ship_loader: StarfleetWorkerShipLoader
) -> None:
    """This tests that the plugin loader's exception handling logic is correct when handling a worker ship plugin with an invalid configuration."""
    from starfleet.utils.configuration import BadConfigurationError

    test_configuration["TestingStarfleetWorkerPlugin"].pop("Enabled")  # Required field -- this will result in a Marshmallow ValidationError
    with pytest.raises(BadConfigurationError) as exc:
        test_worker_ship_loader.get_worker_ships()

    assert str(exc.value) == "[💥] Worker ship: TestingStarfleetWorkerPlugin has an invalid configuration. {'Enabled': ['Missing data for required field.']}"
    assert verify_logger(
        mock_loader_logger, "[💥] Major exception encountered configuring all the Starfleet worker ship plugins. See the stacktrace for details."
    )


def test_send_alerts(mock_slack_api: MagicMock) -> None:
    """This will test that we Ship's send_alert function works properly at sending alerts (to Slack)."""
    from starfleet.worker_ships.ship_schematics import AlertPriority
    from tests.worker_ship_utils.testing_plugins.basic_plugin import TestingStarfleetWorkerPlugin

    ship = TestingStarfleetWorkerPlugin()
    ship.alert_channel = "pewpewpew"

    priorities = [priority for priority in AlertPriority]  # pylint: disable=unnecessary-comprehension
    emoji_map = {
        AlertPriority.PROBLEM: "🚨",
        AlertPriority.IMPORTANT: "📣",
        AlertPriority.SUCCESS: "✅",
        AlertPriority.INFORMATIONAL: "ℹ️",
    }

    # Send alert messages without having an AlertPriority established (the default for the worker ship is AlertPriority.NONE) -- no messages to slack should be sent out:
    for priority in priorities:
        ship.send_alert(priority, "Some message", "some message body")
        assert not mock_slack_api.return_value.chat_postMessage.called

    priorities.remove(AlertPriority.NONE)
    for current_priority in priorities:
        ship.alert_priority = current_priority

        # Verify that we are able to send with the current priority and all the prior ones:
        for priority in priorities:
            mock_slack_api.return_value.chat_postMessage.reset_mock()
            ship.send_alert(priority, "Some message", "some message body")

            # If the current priority is the same or bigger than the message priority sent, then the message should have been sent:
            if current_priority.value >= priority.value:
                assert mock_slack_api.return_value.chat_postMessage.call_args[1]["channel"] == "pewpewpew"
                assert mock_slack_api.return_value.chat_postMessage.call_args[1]["text"].startswith(emoji_map[priority])

            # Otherwise it should not have been sent:
            else:
                assert not mock_slack_api.return_value.chat_postMessage.called
