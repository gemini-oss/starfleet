"""Starfleet's worker "ship" loader.

This does all the logic required to load Starfleet workers (which we call plugins 🚀for fun).

:Module: starfleet.worker_ships.loader
:Copyright: (c) 2022 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
from typing import Dict

import starfleet.worker_ships.plugins
from starfleet.utils.logging import LOGGER
from starfleet.utils.configuration import BadConfigurationError, STARFLEET_CONFIGURATION
from starfleet.utils.plugin_loader import find_plugins
from starfleet.worker_ships.ship_schematics import StarfleetWorkerShip, StarfleetWorkerShipInstance


class InvalidStarfleetWorkerException(Exception):
    """Exception raised if the Starfleet worker ship plugin is NOT a subclass of StarfleetWorkerShip"""


class StarfleetWorkerShipLoader:
    """This will load all the Starfleet worker plugins."""

    # These are defined here for easy testability:
    _worker_ship_path: str = starfleet.worker_ships.plugins.__path__
    _worker_ship_prefix: str = starfleet.worker_ships.plugins.__name__ + "."

    def __init__(self):
        self._worker_ships: Dict[str, StarfleetWorkerShipInstance] = None  # noqa

    def reset(self) -> None:
        """This resets the loader. This is only used as a convenience for unit testing."""
        self._worker_ships = None

    def load_all_plugins(self):
        """
        This will load all Starfleet worker ship plugins and verify that they are set up properly. This is code that will mostly be used by both the
        Starbase and the CLI.
        """
        self._worker_ships = {}

        LOGGER.debug("[📦] Loading worker ship plugins...")
        try:
            for _, plugin_classes in find_plugins(self._worker_ship_path, self._worker_ship_prefix, "WORKER_SHIP_PLUGINS", StarfleetWorkerShip).items():
                for plugin in plugin_classes:
                    LOGGER.debug(f"[🔧] Configuring worker ship: {plugin.get_worker_ship_name()}")  # noqa

                    # Check if the worker has a configuration entry. If not then skip:
                    worker_ship_config = STARFLEET_CONFIGURATION.config.get(plugin.get_worker_ship_name())  # noqa
                    if worker_ship_config:
                        # If there is a configuration entry, then we need to validate the correct configuration:
                        errors = plugin.configuration_template_class().validate(worker_ship_config)  # noqa
                        if errors:
                            raise BadConfigurationError(f"[💥] Worker ship: {plugin.get_worker_ship_name()} has an invalid configuration. {str(errors)}")  # noqa

                        # Check that the worker ship is enabled:
                        if not worker_ship_config["Enabled"]:
                            LOGGER.debug(f"[⏭️] Worker ship: {plugin.get_worker_ship_name()} is DISABLED in it's configuration. Skipping...")  # noqa
                            continue

                        # Instantiate the worker class:
                        self._worker_ships[plugin.get_worker_ship_name()] = plugin()  # noqa
                        LOGGER.debug(f"[👍] Worker ship: {plugin.get_worker_ship_name()} is properly configured and ENABLED.")  # noqa

                    else:
                        LOGGER.debug(f"[⏭️] Worker ship: {plugin.get_worker_ship_name()} has no discovered configuration. Skipping... ")  # noqa
                        continue

        except Exception as exc:
            LOGGER.error("[💥] Major exception encountered configuring all the Starfleet worker ship plugins. See the stacktrace for details.")
            LOGGER.exception(exc)
            raise

        if not self._worker_ships:
            LOGGER.debug("[🤷] There were no properly enabled worker ships to load")
        else:
            LOGGER.debug(f"[🚀] Completed loading {len(self._worker_ships)} worker ships")

    def get_worker_ships(self) -> Dict[str, StarfleetWorkerShipInstance]:
        """This will return all the worker ship instances. This is used by the Starbase and by the CLI."""
        if self._worker_ships is None:
            self.load_all_plugins()

        return self._worker_ships


STARFLEET_WORKER_SHIPS = StarfleetWorkerShipLoader()
